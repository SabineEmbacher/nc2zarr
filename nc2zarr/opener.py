# The MIT License (MIT)
# Copyright (c) 2020 by Brockmann Consult GmbH and contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import glob
import os.path
from typing import List, Optional, Iterator, Callable, Union

import xarray as xr

from .error import ConverterError
from .log import LOGGER
from .log import log_duration


class DatasetOpener:
    def __init__(self,
                 input_paths: Union[str, List[str]],
                 input_multi_file: bool = False,
                 input_sort_by: str = None,
                 input_decode_cf: bool = False,
                 input_concat_dim: str = None,
                 input_engine: str = None):
        self._input_paths = input_paths
        self._input_multi_file = input_multi_file
        self._input_sort_by = input_sort_by
        self._input_decode_cf = input_decode_cf
        self._input_concat_dim = input_concat_dim
        self._input_engine = input_engine

    def open_datasets(self, preprocess: Callable[[xr.Dataset], xr.Dataset] = None) \
            -> Iterator[xr.Dataset]:
        if self._input_multi_file:
            return self._open_mfdataset(preprocess)
        else:
            return self._open_datasets(preprocess)

    def _open_mfdataset(self, preprocess: Callable[[xr.Dataset], xr.Dataset] = None) \
            -> xr.Dataset:
        input_paths = self._resolve_input_paths()
        with log_duration(f'Opening {len(input_paths)} file(s)'):
            ds = xr.open_mfdataset(input_paths,
                                   engine=self._input_engine,
                                   preprocess=preprocess,
                                   concat_dim=self._input_concat_dim,
                                   decode_cf=self._input_decode_cf)
        yield ds

    def _open_datasets(self, preprocess: Callable[[xr.Dataset], xr.Dataset] = None) \
            -> Iterator[xr.Dataset]:
        input_paths = self._resolve_input_paths()
        n = len(input_paths)
        for i in range(n):
            input_file = input_paths[i]
            LOGGER.info(f'Processing input {i + 1} of {n}: {input_file}')
            with log_duration('Opening'):
                ds = xr.open_dataset(input_file,
                                     engine=self._get_engine(input_file),
                                     decode_cf=self._input_decode_cf)
                if preprocess:
                    ds = preprocess(ds)
            yield ds

    def _get_engine(self, input_file: str) -> Optional[str]:
        engine = self._input_engine
        if not engine and input_file.endswith('.zarr') and os.path.isdir(input_file):
            engine = 'zarr'
        return engine

    def _resolve_input_paths(self) -> List[str]:
        input_files = self.resolve_input_paths(self._input_paths, self._input_sort_by)
        if not input_files:
            raise ConverterError('No inputs found.')
        LOGGER.info(f'{len(input_files)} input(s) found:\n'
                    + ('\n'.join(map(lambda f: f'  {f[0]}: ' + f[1],
                                     zip(range(len(input_files)), input_files)))))
        return input_files

    @classmethod
    def resolve_input_paths(cls,
                            input_paths: Union[str, List[str]],
                            sort_by: str = None) -> List[str]:

        resolved_input_files = []
        if isinstance(input_paths, str):
            resolved_input_files.extend(glob.glob(input_paths, recursive=True))
        elif input_paths is not None and len(input_paths):
            for input_path in input_paths:
                resolved_input_files.extend(glob.glob(input_path, recursive=True))

        if sort_by:
            # Get rid of doubles and sort
            resolved_input_files = set(resolved_input_files)
            if sort_by == 'path' or sort_by is True:
                return sorted(resolved_input_files)
            if sort_by == 'name':
                return sorted(resolved_input_files, key=os.path.basename)
            raise ConverterError(f'Can sort by "path" or "name" only, got "{sort_by}".')
        else:
            # Get rid of doubles, but preserve order
            seen_input_files = set()
            unique_input_files = []
            for input_file in resolved_input_files:
                if input_file not in seen_input_files:
                    unique_input_files.append(input_file)
                    seen_input_files.add(input_file)
            return unique_input_files
