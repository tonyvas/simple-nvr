from __future__ import annotations

import os, shutil
from datetime import datetime, timezone

from . import Video

class TempVideo(Video):
    def __init__(self, filepath):
        super().__init__(filepath)

    @staticmethod
    def format_name(utc_datetime, extension):
        return f'{int(utc_datetime.timestamp())}.{extension}'

    def get_datetime(self):
        return datetime.fromtimestamp(int(self.get_filename_no_ext()), tz=timezone.utc)

    def delete(self):
        if not self.exists():
            raise Exception(f'TempVideo does not exist at current location!')

        os.remove(self.get_filepath())