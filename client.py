# -*- coding: utf-8 -*-
import socket
import time
import threading
import logging

from settings import setting


logging.getLogger()


class Client(threading.Thread):
    """
    Класс реализующий клиент для подключения к серверу API Umirs
    """
    def __init__(self, host='', port=0, packetsManager=None):
        threading.Thread.__init__(self)
        self.port = port
        self.host = host
        self.packetsManager = packetsManager
        # служебный флаг для мониторинга текущего соединения клиента драйвера. Необходим, чтобы корректно
        # переподключаться к серверу API, при изменении пар-в подключения.
        self.__clientCon = True
        self.__errorCount = 0  # атрибут кол-ва сетевых ошибок
        self.__ping_time = 1.0  # временной атрибут для таймаута между пингами
        self.__set_ping_time_from_setting()  # установим таймаут между пингами из settings.xml

    def configureClient(self, host=None, port=None):
        self.host = host
        self.port = int(port) if port else None
        self.__clientCon = False
        self.packetsManager.clearQueuesOfPackets()  # очистим очереди входящих и исходящих оборудований


    def __set_ping_time_from_setting(self):
        """
        метод для установки таймаута между пингами из settings.xml
        :return:
        """
        ping_time = 0
        # если такой настройки в файле нет, то оставим таймаут по умолчанию
        try:
             ping_time = setting['net']['ping_time']
        except Exception as e:
            logging.exception(str(e))
            logging.info(f'set default ping_time={self.__ping_time}')
        else:
            self.__ping_time = ping_time
            logging.info(f'set from settings.xml ping_time={self.__ping_time}')

    def connect(self):
        """
        Метод подключения к серверу API Umirs
        :return:
        """
        while True:
            # ожидаем пока не проиницилизируются host и port для корректного подключения
            if not self.host and not self.port:
                logging.info("Host and port does not set")
                time.sleep(3.0)
                continue
            # флаг newConnection необходимо отслеживать при первом подключении к серверу API, т.к. первым должен быть
            # отправлен пакет приветствия
            newConnection = True
            try:
                logging.info(f'Try connect to Server API Umirs: {self.host}:{self.port}')
                soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                soc.connect((self.host, self.port))
            except Exception as e:
                logging.error('Connection to Server API Umirs is lost')
                logging.exception(f'Exception: {str(e)}')
            else:
                # как только появилось соединение, установим параметр сокету, чтобы он был не блокирующим
                soc.setblocking(False)
                self.__clientCon = True
                # счётчик пустых пакетов (имеется в виду пакеты пинга). Данный счётчик нужен для того, чтобы понять жив
                # ли поток, который генерирует эти патеки
                emptyPacketCounter = 0
                # сбросим кол-во сетевых ошибок
                self.resetErrorCount()
                # запустим потоки для генерации пинг пакетов и декодирования входящих пакетов от Umirs
                self.packetsManager.startThreads()

                while self.__clientCon:
                    # если соединения устанавливается впервые, или произошло переподключение, необходимо отправить
                    # пакет приветствия сервера API
                    if newConnection:
                        packet = self.packetsManager.getHelloPacket()
                        newConnection = False
                        # перед новым подключением очистим очереди пакетов
                        self.packetsManager.clearQueuesOfPackets()
                    # если соединение в пределах одной сессии, то просто берем сообщения из очереди исх-х пакетов
                    else:
                        packet = self.packetsManager.getOutComingPacket()

                    if packet:
                        # если пакет есть обнулим счётчик пустых пакетов
                        emptyPacketCounter = 0
                        try:
                            logging.info('try to send packet to Umirs')
                            soc.send(packet)
                            logging.info('packet sent successfully')
                        except BlockingIOError:
                            logging.info('Failed to sent packet to Umirs')
                            # если возникли проблемы с отправкой пакета увеличим счётчик сетевых пакетов
                            self.increaseErrorCount()
                        try:
                            logging.info('try 1 to receive response packet from Umirs')
                            incomPacket = soc.recv(1024)
                            # Если по какой-то причине входящий пакет None, залогируем другой вывод
                            if incomPacket is None:
                                logging.info(f'response packet received successfully. Length packet=None')
                            else:
                                logging.info(f'response packet received successfully. Length packet={len(incomPacket)}')
                            if incomPacket is None or len(incomPacket) == 0:
                                logging.info('Server API Umirs has sent zero length packet. It means'
                                             ' Server API Umirs turning off.')
                                logging.info('Connection will be close and driver Umirs will be restart')
                                break
                        # except socket.timeout:
                        except BlockingIOError:
                            logging.info('Failed to receive response packet from Umirs')
                            # если возникли проблемы с получением пакета увеличим счётчик сетевых пакетов
                            self.increaseErrorCount()
                        except Exception:
                            logging.exception('Connection to Server API Umirs is lost')
                            break
                        else:
                            if len(incomPacket) == 0:
                                # если входящих пакет пуст, увеличим кол-во сетевых ошибок
                                self.increaseErrorCount()
                            else:
                                # если пакет с полезными данными, то уменьшим кол-во сетевых ошибок
                                self.reduceErrorCount()
                            self.packetsManager.addIncomingPacket(incomPacket)

                    # если пакетов на отправку нет, послушаем сокет, может сервер прислал пакет
                    else:
                        # если пакета нет - увеличим кол-во пустых пакетов
                        emptyPacketCounter += 1

                        try:
                            logging.info('try 2 to receive response packet from Umirs')
                            incomPacket = soc.recv(1024)
                            if incomPacket is None:
                                logging.info(f'response packet received successfully. Length packet=None')
                            else:
                                logging.info(f'response packet received successfully. Length packet={len(incomPacket)}')
                            if incomPacket is None or len(incomPacket) == 0:
                                logging.info('Server API Umirs has sent zero length packet. It means'
                                             ' Server API Umirs turning off.')
                                logging.info('Connection will be close and driver Umirs will be restart')
                                break
                        except BlockingIOError:
                            logging.info('Failed to receive response packet from Umirs')
                            self.increaseErrorCount()
                            pass
                        else:
                            # пустые пакеты не добавляем в очередь входящих пакетов.
                            # (при откючении сервер АPI Umirs отправляет множество пустых пакетов)
                            if incomPacket:
                                self.reduceErrorCount()
                                self.packetsManager.addIncomingPacket(incomPacket)
                            else:
                                self.increaseErrorCount()

                        # если пустых пакетов набралось больше 20, значит поток отправляющий пакеты для пинга, аварийно
                        # завершился. Нужно запустить этот поток ещё раз.
                        if emptyPacketCounter > 100:
                            emptyPacketCounter = 0
                            logging.info('Max count empty packet. Counter is reset')
                            self.packetsManager.startPingThread()

                    # если кол-во сетевых ошибок превысило максимум, значит сервер ПО Umirsа не отвечает на наши
                    # пинг пакеты, при этом сокет еще жив. Поэтому нужно выйти из цикла, тем самым закрыв прежний
                    # сокет и инициировать новое подключение
                    if self.isMaxErrorCount():
                        logging.info('Max number off network errors is reached!')
                        logging.info('Driver Umirs will be restart...')
                        break

                    time.sleep(self.__ping_time)
                self.packetsManager.stopThreads()
                soc.close()  # при корректном выходе из цикла, закроем сокет
                Connection.closeConnection()  # уст. флаг текущего соединения в False
            logging.info('Before start new connection WAIT 15 seconds...')
            time.sleep(15.0)

    def run(self) -> None:
        self.connect()

    def increaseErrorCount(self):
        """
        Метод увеличивает кол-во сетевых ошибок при неуспешной отправке или получения сообщения из сокета
        :return:
        """
        self.__errorCount += 1

    def reduceErrorCount(self):
        """
        Метод уменьшает кол-во сетевых ошибок при неуспешной отправке или получения сообщения из сокета
        :return:
        """
        # если кол-во ошибок равно нулю, то нет смысла их уменьшать
        if self.__errorCount <= 0:
            pass
        else:
            # уменьшене кол-ва сетевых ош. на 5, выбрано исходя из наблюдений, т.к. если Umirs присылыет ответы
            # только на пинг пакеты, то таких пакетов приходит меньше, чем успешных запросов на чтение\отправку данных в
            # сокет. Получается, что при такой ситуации кол-во ошибок будет быстрее накапливаться, и произойдёт разрыв
            # сокета и новое подключение
            self.__errorCount -= 5
            # при уменьшении кол-ва ошибок, может получится что итоговое число стало отрицательным, нужно тогда
            # присвоить 0 (ну исходя из логических рассуждений)
            if self.__errorCount < 0:
                self.__errorCount = 0

    def isMaxErrorCount(self):
        """
        Метод для проверки достигнуто ли максимальное кол-во сетевых ошибок.
        :return:
        """
        logging.debug(f'NETWORK ERROR COUNT: {self.__errorCount}')
        # число 150, подобрано тоже из эксперементальных наблюдений. При отключении ПО Umirs отправляет порядка 100
        # пустых сообщений в сокет, поэтому взято значение - 150, чтобы точно гарантировать своевременное отключение от
        # Umirs. Т.к. в таком случае, точно ясно, что Umirs не отвечает на наши пакеты
        if self.__errorCount > 150:
            return True
        else:
            return False

    def resetErrorCount(self):
        """
        Метод сброса счётчика сетевых ошибок
        :return:
        """
        self.__errorCount = 0


class Connection:
    """
    Статический класс представляющий объект соединения клиента драйвера с сервером API Umirs. Применяется для
    синхронизации состояния текущего соединения в разных потоках (менеджер команд, клиент драйвера)
    """
    _con = False  # соединение по умолчанию отключено

    @staticmethod
    def closeConnection():
        """
        Метод для фиктивного закрытия соединения. Значение текущего соединения обнуляется
        :return:
        """
        Connection._con = False

    @staticmethod
    def startConnection():
        """
        Метод для установления флага текущего соединения
        :return:
        """
        Connection._con = True

    @staticmethod
    def isAlive():
        """
        Метод проверяет есть ли текущее соединение с сервером API Umirs
        :return:
        """
        return Connection._con is True
