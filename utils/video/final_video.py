from __future__ import annotations

import os, shutil
from datetime import datetime, timezone

from . import Video

class FinalVideo(Video):
    def __init__(self, filepath):
        super().__init__(filepath)

    @staticmethod
    def format_name(utc_datetime, local_datetime, extension):
        utc_str = int(utc_datetime.timestamp())
        local_date_str = f'{local_datetime.year:04}{local_datetime.month:02}{local_datetime.day:02}'
        local_time_str = f'{local_datetime.hour:02}{local_datetime.minute:02}{local_datetime.second:02}'

        return f'{local_date_str}_{local_time_str}_{utc_str}.{extension}'

    def get_datetime(self):
        TIMESTAMP_PART_INDEX = 2

        parts = self.get_filename_no_ext().split('_')

        if len(parts) > TIMESTAMP_PART_INDEX:
            # If using new format
            timestamp_str = parts[TIMESTAMP_PART_INDEX]
            return datetime.fromtimestamp(int(timestamp_str), tz=timezone.utc)
        else:
            # Legacy %s.mp4 format
            return datetime.fromtimestamp(int(parts[0]), tz=timezone.utc)

    def get_datetime_local(self):
        date_str, time_str, _ = self.get_filename_no_ext().split('_')

        year = date_str[0:4]
        month = date_str[4:6]
        day = date_str[6:8]

        hour = time_str[0:2]
        mins = time_str[2:4]
        secs = time_str[4:6]

        return datetime(year, month, day, hour, mins, secs)

    def get_thumbnail_path(self):
        return os.path.join(self.get_dirpath(), f'{self.get_filename_no_ext()}.jpg')

    def delete(self, remove_dir=False):
        if not self.exists():
            raise Exception(f'Video does not exist at current location!')

        if os.path.exists(self.get_thumbnail_path()):
            os.remove(self.get_thumbnail_path())
            
        super().delete(remove_dir)
