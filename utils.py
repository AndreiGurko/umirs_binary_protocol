"""
Модуль общих утилит
"""
import time

from datetime import datetime


class TimeUtil:
    @staticmethod
    def get_seconds_from_timestamp_with_tz(timestamp: str):
        """
        Метод для конвертации временной метки с таймзоной в секунды
        :param timestamp:
        :return:
        """
        MICROSECONDS_PREFIX = '.'
        if MICROSECONDS_PREFIX in timestamp:
            return time.mktime(time.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%f%z'))
        return time.mktime(time.strptime(timestamp, '%Y-%m-%dT%H:%M:%S%z'))

    @staticmethod
    def convert_timestamp_to_utc_timestamp(timestamp: str):
        """
        Конвертирует временную метку в utc формат
        :param timestamp: исходная временная метка
        :return:
        """
        # получим секунды из временной метки
        time_from_timestamp = TimeUtil.get_seconds_from_timestamp_with_tz(timestamp)
        # получим временную метку в формате utc
        # !!!! подразумевается, что клиент, который передал временную метку в одной часовой зоне с сервером
        # т.к. при переводе в utc формат сервер смотрит на свою времненую зону, где он находится
        return datetime.utcfromtimestamp(time_from_timestamp).strftime('%Y-%m-%dT%H:%M:%SZ')

    @staticmethod
    def get_seconds_in_local_tz_from_utc_timestamp(timestamp: str):
        """
        Возвращает время в секундах с учётом локальной часовой зоны из временной метки по UTC
        :param timestamp:
        :return:
        """
        utc_time_seconds = TimeUtil.get_seconds_from_timestamp_with_tz(timestamp)
        return utc_time_seconds - time.timezone

    @staticmethod
    def get_current_time():
        return time.time()

    @staticmethod
    def get_unix_timestamp():
        """
        Возвращает unix (utc) временную метку. Время с начала эпохи
        :return:
        """
        return int(datetime.utcnow().timestamp())
