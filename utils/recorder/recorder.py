import threading, subprocess, os, psutil, shutil, json
from time import sleep
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..logger import loggerManager
from ..video import FinalVideo, TempVideo

class Recorder:
    _TEMP_EXTENSION = 'mkv'
    _FINAL_EXTENSION = 'mp4'

    def __init__(self, name:str, storage_dirpath:str, source:str, timezone:str, segment_duration_sec:int, record_audio:bool=True):
        self._name = name
        self._storage_dirpath = storage_dirpath
        self._source = source
        self._timezone = timezone
        self._segment_duration_sec = segment_duration_sec
        self._record_audio = record_audio
        
        self._logger = loggerManager.new_logger(f'recorder-{name}')
        self._is_running = False

        self._threads = [
            threading.Thread(target=self._start_video_mover, daemon=True),
            threading.Thread(target=self._start_ffmpeg, daemon=True),
        ]
        self._ffmpeg = None

        self._video_dirpath = os.path.join(storage_dirpath, 'videos')
        self._temp_dirpath = os.path.join(storage_dirpath, 'temp')


    def is_running(self):
        return self._is_running

    def get_videos(self):
        videos = []

        # Walk over the files in output directory
        for dirpath, dirnames, filenames in os.walk(self._video_dirpath):
            for filename in filenames:
                # Ignore non-video files
                if not filename.endswith('.'+self._FINAL_EXTENSION):
                    continue

                videos.append(FinalVideo(os.path.join(dirpath, filename)))

        # Return videos ordered by date
        return sorted(videos)

    def start(self):
        try:
            self._logger.log_info('Starting recorder')

            if self.is_running():
                # Prevent multiple instances
                raise Exception(f'Recorder is already running!')

            # Set flag
            self._is_running = True
            
            for thread in self._threads:
                thread.start()

            self._logger.log_info('Recorder started!')

            for thread in self._threads:
                thread.join()
        except Exception as e:
            message = f'Failed to start: {e}'
            self._logger.log_critical(message)
            raise Exception(message)

    def stop(self):
        try:
            self._logger.log_info('Stopping recorder')

            # Clear flag
            self._is_running = False

            if self._ffmpeg is not None:
                # Stop FFmpeg subprocess if it is running
                self._logger.log_info('Terminating FFmpeg subprocess')
                self._ffmpeg.terminate()
                self._ffmpeg.wait()

            self._logger.log_info('Waiting for background threads to finish')
            for thread in self._threads:
                thread.join()

            try:
                self._logger.log_info('Cleaning up temporary videos')
                self._move_completed_temp_videos()
            except Exception as e:
                self._logger.log_warning('Failed to clean up temporary videos')

            self._logger.log_info('Recorder stopped!')
        except Exception as e:
            message = f'Failed to stop: {e}'
            self._logger.log_critical(message)
            raise Exception(message)

    def _start_video_mover(self):
        self._logger.log_info(f'Starting video mover')

        # Create directories if needed
        os.makedirs(self._temp_dirpath, exist_ok=True)
        os.makedirs(self._video_dirpath, exist_ok=True)

        while self.is_running():
            try:
                self._move_completed_temp_videos()
            except Exception as e:
                self._logger.log_error(f'Failed to run mover: {e}')
            finally:
                sleep(5)

    def _start_ffmpeg(self):
        ffmpeg_cmd = self._generate_ffmpeg_command()
        os.makedirs(self._temp_dirpath, exist_ok=True)

        while self.is_running():
            try:
                self._logger.log_info(f'Starting FFmpeg subprocess')

                self._ffmpeg = subprocess.Popen(ffmpeg_cmd, text=True, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                while self._ffmpeg.poll() is None:
                    line = self._ffmpeg.stderr.readline().rstrip()
                    if line:
                        self._logger.log_debug(f'FFmpeg: {line}')
            except Exception as e:
                self._logger.log_error(f'Failed to run FFmpeg subprocess: {e}')
            finally:
                sleep(5)

    def _generate_ffmpeg_command(self):
        RTSP_ARGS = ['-rtsp_transport', 'tcp']
        LOG_ARGS = ['-loglevel', 'error']
        INPUT_ARGS = ['-i', self._source]
        VCODEC_ARGS = ['-c:v', 'copy']
        ACODEC_ARGS = ['-c:a', 'aac']
        NO_ACODEC_ARGS = ['-an']
        SEGMENT_ARGS = [
            '-f', 'segment',
            '-segment_time', str(self._segment_duration_sec),
            '-strftime', '1',
            '-segment_atclocktime', '1',
            '-reset_timestamps', '1'
        ]
        OUTPUT_ARGS = ['-y', os.path.join(self._temp_dirpath, '%s.mkv')]

        cmd = ['ffmpeg']

        for arg_list in [ RTSP_ARGS, LOG_ARGS, INPUT_ARGS, VCODEC_ARGS ]:
            for arg in arg_list:
                cmd.append(arg)
        
        if self._record_audio:
            for arg in ACODEC_ARGS:
                cmd.append(arg)
        else:
            for arg in NO_ACODEC_ARGS:
                cmd.append(arg)

        for arg_list in [ SEGMENT_ARGS, OUTPUT_ARGS ]:
            for arg in arg_list:
                cmd.append(arg)

        return cmd

    def _move_completed_temp_videos(self):
        MIN_FILE_SIZE_BYTES = 10e3 # 10KB

        # For each completed .mkv file
        for temp_mkv_video in self._get_completed_temp_videos():
            temp_mkv_path = temp_mkv_video.get_filepath()

            try:
                self._logger.log_info(f'Moving {temp_mkv_video.get_filename()}')

                # Get all paths
                utc_datetime = temp_mkv_video.get_datetime()
                local_datetime = utc_datetime.astimezone(ZoneInfo(self._timezone))

                temp_mp4_path = temp_mkv_path.replace('.'+self._TEMP_EXTENSION, '.'+self._FINAL_EXTENSION)
                
                final_mp4_name = FinalVideo.format_name(utc_datetime, local_datetime, self._FINAL_EXTENSION)
                final_mp4_dir = local_datetime.date().isoformat()
                final_mp4_path = os.path.join(self._video_dirpath, final_mp4_dir, final_mp4_name)
                final_mp4_video = FinalVideo(final_mp4_path)

                # Make directory for final path
                os.makedirs(os.path.dirname(final_mp4_path), exist_ok=True)

                try:
                    # Convert temp mkv to mp4
                    self._logger.log_debug('Converting MKV to MP4')
                    self._mkv_to_mp4(temp_mkv_path, temp_mp4_path)
                except Exception as e:
                    raise Exception(f'Failed to convert temporary to final video: {e}')
                
                try:
                    # Move mp4 from temp to final directory
                    self._logger.log_debug('Moving video into directory structure')
                    shutil.move(temp_mp4_path, final_mp4_path)
                except Exception as e:
                    raise Exception(f'Failed to move final video into directory structure: {e}')
                
                try:
                    self._logger.log_debug('Generating thumbnail')
                    self._generate_thumbnail(final_mp4_path, final_mp4_video.get_thumbnail_path())
                except Exception as e:
                    self._logger.log_warning(f'Failed to create thumbnail: {e}')

                try:
                    # Delete original temp mkv
                    self._logger.log_debug('Deleting temporary video')
                    temp_mkv_video.delete()
                except Exception as e:
                    raise Exception(f'Failed to remove temporary video: {e}')

                self._logger.log_debug('Video moved!')
            except Exception as e:
                self._logger.log_error(f'Failed to move {temp_mkv_video.get_filename()}: {e}')

                # If file is very small, delete it
                if temp_mkv_video.exists() and temp_mkv_video.get_size() < MIN_FILE_SIZE_BYTES:
                    self._logger.log_warning(f'Temp video {temp_mkv_video.get_filename()} appears broken, deleting')
                    temp_mkv_video.delete()

    def _get_completed_temp_videos(self):
        videos = []
        
        # Scan temp video dir
        for filename in os.listdir(self._temp_dirpath):
            if not filename.endswith('.'+self._TEMP_EXTENSION):
                # Skip if not video
                continue

            video = TempVideo(os.path.join(self._temp_dirpath, filename))
            if not video.is_open():
                # If no other process (ffmpeg) has this video open, assume it's done
                videos.append(video)

        return sorted(videos)

    def _mkv_to_mp4(self, input_path, output_path):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        ffmpeg_cmd = [
            'ffmpeg',
            '-loglevel', 'error',
            '-threads', '2',
            '-i', input_path,
            '-c', 'copy',
            '-y', output_path
        ]

        proc = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            stderr = proc.stderr.decode('utf-8')
            raise Exception(f'Failed to convert MKV to MP4: {stderr}')

    def _generate_thumbnail(self, video_path, thumb_path):
        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        cmd = [
            'ffmpeg', '-y',
            '-i', f'{video_path}',
            '-ss', '1',
            '-vframes', '1',
            '-s', '720x480',
            '-q:v', '2',
            f'{thumb_path}'
        ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            stderr = proc.stderr.decode('utf-8')
            raise Exception(f'Failed to generate thumbnail: {stderr}')
