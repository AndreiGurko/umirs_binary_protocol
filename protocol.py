import time
import logging

from threading import Thread
from client import Connection


logging.getLogger()

FOR_SERVER = 0x00
FOR_CLIENT = 0x01
PROTOCOL_VERSION = 0x01  # версия протокола
CLIENT_ID = 0x01  # согласно протоколу пока все 0x01


class BinProtocol:
    """
    Класс реализующий бинарный протол Umirs
    """
    def __init__(self, packetsManager=None, eventsManager=None, serverId=1):
        """
        :param packetsManager: ссылка на менеджер пакетов
        :type packetsManager: PacketsManager
        :param self.__countPacket: счётчик исходящих пакетов
        :type self.__countPacket: int
        :param self.__ping: метод для пинга сервера в отдельном потоке
        :type self.__ping: Thread
        """
        self.__countPacket = 0
        self.packetsManager = packetsManager
        self.eventsManager = eventsManager
        self.serverId = serverId
        self.__ping = None  # атрибут для потока, который будет отправлять пинговые сообщения
        self.__parsePacket = None  # атрибут для потока, который будет декодировать полученные сообщения от Umirs
        self.__live = True  # флаг, чтобы обеспечить выход из бесконечных циклов. Нужен для корректности вып-я тестов
        self.pingLive = True

    def sayHello(self, ping=False):
        """
        Команда отправки пакета приветствия сервера
        длина пакета: 0x0A
        команда: 0x00
        длина команды: 0x01
        :param: ping - флаг, указывающий для каких целей формируется пакет приветствия. Если флаг True - это значит,
        что не нужно добавлять пакет приветствия сервера в общую очередь пакетов, необходимо просто вернуть пакет.
        Это необходимо сделать для корректного подключения к серверу API
        :return: packet | bytearray
        """
        packet = self.__makePacket(lengthPacket=0x0A, command=0x00, lengthCommand=0x01)
        packet.append(PROTOCOL_VERSION)
        if ping:
            self.packetsManager.addOutcomingPacket(packet)
            return packet

    def getServerStatus(self, params):
        """
        Команда отправки пакета для получения статуса сервера
        длина пакета: 0x0A
        команда: 0x09
        длина команды: 0x01
        :return:
        """
        packet = self.__makePacket(lengthPacket=0x0A, command=0x09, lengthCommand=0x01)
        packet.append(params.get('formatStatus', 0))
        return packet

    def captureAndFollowTarget(self, params):
        """
        Команда отправки пакета для принудительного захвата и сопровождения на сервере траектории с определенным ID
        длина пакета: 0x0C
        команда: 0x0B
        длина команды: 0x03
        :return:
        """
        if params.get('trackId') is None or params.get('captureTarget') is None:
            return None
        packet = self.__makePacket(lengthPacket=0x0C, command=0x0B, lengthCommand=0x03)
        trackId = params['trackId']
        # если ID трека больше, чем байт, то необходимо это число разбить на старший и младший байты
        packet.append(trackId >> 8)
        packet.append(trackId & 0b0000000011111111)
        packet.append(params['captureTarget'])
        self.packetsManager.addOutcomingPacket(packet)
        return packet

    def setAutoCaptureTarget(self, params):
        """
        Команда отправки пакета для переключения режима автозахвата траектории на сервере
        длина пакета: 0x0A
        команда: 0x0C
        длина команды: 0x01
        :return:
        """
        if params.get('setAutoCapture') is None:
            return None
        packet = self.__makePacket(lengthPacket=0x0A, command=0x0C, lengthCommand=0x01)
        packet.append(params['setAutoCapture'])
        self.packetsManager.addOutcomingPacket(packet)
        return packet

    def setArmRLS(self, params):
        """
        Команда отправки пакета для постановки/снятия на охрану РЛС. При этом включается/выключается излучение
        передатчика РЛС
        длина пакета: 0x0A
        команда: 0x0E
        длина команды: 0x01
        :return:
        """
        if params.get('setArmRLS') is None:
            return None
        packet = self.__makePacket(lengthPacket=0x0A, command=0x0E, lengthCommand=0x01)
        packet.append(params['setArmRLS'])
        self.packetsManager.addOutcomingPacket(packet)
        return packet

    def setFiltersOfTargets(self, params):
        """
        Команда отправки пакета для управления фильтрами траекторий на сервере
        длина пакета: 0x0A
        команда : 0x0F
        длина команды: 0x01
        :return:
        """
        if params.get('setFilters') is None:
            return None
        packet = self.__makePacket(lengthPacket=0x0A, command=0x0F, lengthCommand=0x01)
        packet.append(params['setFilters'])
        self.packetsManager.addOutcomingPacket(packet)
        return packet

    def setMasksOfTargets(self, params):
        """
        Команда отправки пакета для управления масками траекторий на сервере
        длина пакета: 0x0A
        команда : 0x10
        длина команды: 0x01
        :return:
        """
        if params.get('setMasks') is None:
            return None
        packet = self.__makePacket(lengthPacket=0x0A, command=0x10, lengthCommand=0x01)
        packet.append(params['setMasks'])
        self.packetsManager.addOutcomingPacket(packet)
        return packet

    def setPTZ(self, params):
        """
        Команда отправки пакета для управления положением PTZ поворотного устр-ва. Для выполнения данной команды,
        автозахват траекторий на сервере должен быть выключен, иначе команда игнорируется сервером
        длина пакета: 0x0B
        команда : 0x11
        длина команды: 0x02
        """
        if params.get('setPTZCommand') is None or params.get('setPTZSpeed') is None:
            return None
        packet = self.__makePacket(lengthPacket=0x0B, command=0x11, lengthCommand=0x02)
        packet.append(params['setPTZCommand'])
        packet.append(params['setPTZSpeed'])
        self.packetsManager.addOutcomingPacket(packet)
        return packet

    def setPTZPreset(self, params):
        """
        Команда отправки пакета для вызова или установки пресета PTZ поворотного устройства Umirs.
        !!!
        Пресет действует только для поворотного устройства и не управляет приближением IP-камеры
        !!!
        длина пакета: 0x0B
        команда : 0x12
        длина команды: 0x02
        :return:
        """
        if params.get('presetId') is None or params.get('setPTZPreset') is None:
            return None
        packet = self.__makePacket(lengthPacket=0x0B, command=0x12, lengthCommand=0x02)
        packet.append(params['presetId'])  # номер предустановки от 1 до 25
        packet.append(params['setPTZPreset'])
        self.packetsManager.addOutcomingPacket(packet)
        return packet

    def setServerId(self, serverId):
        """
        Метод для установки значения Id сервера API Umirs.
        :param serverId:
        :return:
        """
        self.serverId = serverId
        # изменив Id сервера API Umirs, необходимо обновить пакет для приветствия
        self.packetsManager.setHelloPacket(self.sayHello(ping=True))

    def _setCountPacket(self):
        """
        метод для присвоения порядкового номера пакету перед отправкой. Может генерировать значения от 0 до 255
        :return:
        """
        self.__countPacket = (self.__countPacket % 256) + 1
        if self.__countPacket == 256:
            self.__countPacket = 0
        return self.__countPacket

    def __pingServerAPI(self, **params):
        """
        Метод для пинга сервера API Umirs. Каждые 3 секунды на сервер API будет отправляться сообщение с запросом о
        статусе сервера. Тем самым, согласно протоколу, сервер будет понимать, что клиент все еще на связи и не будет
        обрывать соединение.
        :param params:
        :return:
        """
        logging.info("START PING PACKET thread")
        # перед запуском цикла пинга зададим сообщение приветствия
        self.packetsManager.setHelloPacket(self.sayHello(ping=True))
        # счётчик отосланных пакетов
        countDownToHelloPacket = 0
        while self.__live and self.pingLive:
            packet = self.getServerStatus(params)
            self.packetsManager.addOutcomingPacket(packet)
            logging.info('added PING packet into manager')
            time.sleep(3.0)
            countDownToHelloPacket += 1
            # на каждые 5 пакетов пинга вставляем один пакет приветствия
            if countDownToHelloPacket > 5:
                countDownToHelloPacket = 0
                self.packetsManager.setHelloPacket(self.sayHello(ping=True))
                logging.info('added HELLO packet into manager')
        logging.info('FINISHED PING PACKET thread')

    def startNewPingPacketThread(self):
        """
        Метод для запуска нового потока отправки пинг пакетов в сервер API Umirs
        :return:
        """
        # если драйвер запускается впервые сделаем проверку атрибута на None
        if self.__ping is None:
            self.__parsePacket = Thread(target=self.__pingServerAPI, args=({}))
            self.__parsePacket.start()
            return
        # если предыдущий поток еще жив, уст. значение флага pingLive=False, таким образом метод отправки пинга выйдет
        # из бесконечного цикла
        # этот сценарий с флагом pingLive нужен для того, если поток отправки пинга аварийно завершился, и нам нужно
        # его перезапустить
        if self.__ping.is_alive():
            self.pingLive = False
            self.__ping.join(3.0)
            logging.info("Previously PING PACKET Thread is stopped")
            self.pingLive = True
        self.__ping = Thread(target=self.__pingServerAPI, args=({}))
        self.__ping.start()

    def turnOffFlagForThreads(self):
        """
        Метод для сброса флага, который используется в бесконечных циклах методов: отправки пинговых сообщений, декодиро
        вания полученных сообщений из Umirs
        :return:
        """
        self.__live = False

    def turnOnFlagForThreads(self):
        """
        Метод для установки флага, который используется в бесконечных циклах методов: отправки пинговых сообщений,
         декодирования полученных сообщений из Umirs
        :return:
        """
        self.__live = True

    def startDecodePacketsThread(self):
        """
        Метод для запуска потока в котором декодируются сообщения от Umirs
        :return:
        """
        # если драйвер запускается впервые сделаем проверку атрибута на None
        if self.__parsePacket is None:
            self.__parsePacket = Thread(target=self.decodeIncomingPackets)
            self.__parsePacket.start()
            return
        elif self.__parsePacket.is_alive():
            self.__parsePacket.join(3.0)
        self.__parsePacket = Thread(target=self.decodeIncomingPackets)
        self.__parsePacket.start()

    def __makePacket(self, lengthPacket, command, lengthCommand):
        """
        Метод создает пакет для отправки и заполняет некоторые поля
        :return: packet | bytearray
        """
        packet = bytearray()
        packet.append(FOR_SERVER)
        packet.append(0x00)  # под длину пакета зарезервировано протоколом 2 байта
        packet.append(lengthPacket)  # общая длина пакета
        packet.append(self._setCountPacket())
        packet.append(CLIENT_ID)
        packet.append(self.serverId)
        packet.append(command)  # номер команды, которую необходимо выполнить
        packet.append(0x00)  # под длину команды зарезервировано 2 байта
        packet.append(lengthCommand)  # длина команды 2 байта

        return packet

    def decodeIncomingPackets(self):
        """
        Метод для декодирования входящих пакетов
        :return:
        """
        logging.info('START DECODE Packets Thread')
        buffer = bytearray()  # буфер для хранения неполных пакетов
        while self.__live:
            if not Connection.isAlive():
                # если нет текущего соединения, то отправляем None в метод для парсинга пакетов сост-й сервера API
                self.__parseServerStatePacket(None)

            incomPacket = self.packetsManager.getIncomingPacket()

            if incomPacket:
                # дебаговый принт, можно потом убрать
                logging.info(f'Decode packet length={len(incomPacket)}')
                # для удобства обработки сформируем массив байтов из байтового пакета
                incomPacket = bytearray(incomPacket)
                if buffer:
                    buffer.extend(incomPacket)
                    incomPacket = buffer
                    # затем обнулим буфер
                    buffer = bytearray()
                # чтобы корректно извлечь данные о длине пакета, длина данных должны быть больше 2х элементов, т.к.
                # в индексах [1] и [2] хранится общая длина пакета.
                while len(incomPacket) > 2:
                    lengthPacket = (incomPacket[1] << 8) + incomPacket[2]
                    # если длина пакета больше 416 байт (это максимальная длина пакета согласно протоколу), или равна
                    # нулю то обнулим буфер и обнулим данные входящего пакета, затем выйдем из цикла обработки сообщений
                    if lengthPacket > 416 or lengthPacket == 0:
                        buffer = bytearray()
                        incomPacket = None
                        logging.info('Length packet is more than 416 bytes!' if lengthPacket > 0 else
                                     'Received wrong packet')
                        break
                    # если пакет пришел целиком, то извлекаем его
                    if lengthPacket <= len(incomPacket):
                        packet = bytearray([incomPacket.pop(0) for _ in range(lengthPacket)])
                        # передадим извлеченный пакет в метод, который проведет дальнейший его парсинг
                        if packet:
                            self.__parseIncomingPackets(packet)
                    else:
                        # если во входящих данных пакет пришел не целиком или после извлечения пакета из данных остались
                        # данные представлюящие не полный пакет, то запоминаем эту часть, чтобы потом добавить к
                        # следующей части полученных данных
                        for _ in range(len(incomPacket)):
                            buffer.append(incomPacket.pop(0))
                        break
                # для корректной отработки ситуаций, когда данные приходят меньше 3х байт, или же после извлечения
                # целого пакета из данных остаётся меньше 2х байт, нужно сохранять всё в буфере, чтобы в итоге составить
                # корректный пакет
                if incomPacket and len(incomPacket):
                    for _ in range(len(incomPacket)):
                        buffer.append(incomPacket.pop(0))
            else:
                # дебаговый принт, можно потом убрать
                logging.info(f'Decode packet empty')
                time.sleep(0.5)
        logging.info('FINISHED DECODE Packets Thread')

    def __parseIncomingPackets(self, packet):
        """
        Метод для парсинга входящего пакета
        :param packet:
        :return:
        """
        # 0x01 - команда приветствия сервера
        # 0x0A - команда передачи траекторий
        # 0x0D - команда статуса захвата трека
        # 0x14 - команда статуса сервера
        # 0x15 - команда расширенного статуса сервера

        if packet[6] == 0x01:
            return self.__parseHelloClientPacket(packet)
        elif packet[6] == 0x0A:
            return self.__parseTrajectoriesDiscoveredDisplayPacket(packet)
        elif packet[6] == 0x0D:
            return self.__parseTargetCaptureStateDisplayPacket(packet)
        elif packet[6] == 0x14:
            return self.__parseServerStatePacket(packet)
        elif packet[6] == 0x15:
            return self.__parseServerExtentedStatePacket(packet)

        logging.info('Can not decode packet with command {}'.format(packet[6]))
        return

    def __parseHelloClientPacket(self, packet):
        """
        Метод для парсинга пакета от сервера, который отвечает на приветствие сервера. В этом методе проверяется
        совместимость протоколов.
        :param packet:
        :return:
        """
        # пакет 3.3, 0x01 - команда приветствия сервера
        logging.info('Received Hello packet from Server API Radescan')
        if packet[9] == 0x00:
            raise Exception(f'Radescans Server API protocol version is not compatible with Ports protocol version.'
                            f' Ports version={PROTOCOL_VERSION}')
        elif packet[9] > 0:
            # если в 9м байте значение больше нуля, то всё ок, протоколы совместимы. Установим состояние соединения в
            # True
            Connection.startConnection()
            self.eventsManager.connectToServerRadescan()

    def __parseTrajectoriesDiscoveredDisplayPacket(self, packet):
        """
        Метод для парсинга пакета отображения обнаруженных траекторий
        :param packet:
        :return:
        """
        # пакет 3.5, 0x0A - команда передачи траекторий
        # print('0x0A - команда передачи траекторий')
        logging.debug('Received packet 3.5 {} length of packet = {}'.format(packet, len(packet)))

        trajectoriesCount = packet[9]
        index = self.__byteIndex()  # получим генератор индексов для перемещения по байтовому массиву
        trajectoriesData = {}
        for trajectoryId, _ in enumerate(range(trajectoriesCount), 1):
            track = {}
            # вычислим номер трека
            trackId = (packet[next(index)] << 8) + packet[next(index)]
            track['trackId'] = trackId
            # признак захвата цели
            track['status'] = packet[next(index)]
            # вычислим ЭПР (эффективная площадь рассеивания). Она закодированна двумя байтами: целой и дробной частями
            intPart = packet[next(index)]
            fractionalPart = packet[next(index)]
            track['square'] = float(f'{intPart}.{fractionalPart}')
            # вычислим дальность до цели
            track['range'] = (packet[next(index)] << 8) + packet[next(index)]
            # Вычислим азимут. Точность 0.5 градуса. Знаковое целое, кодирование в доп-м коде
            # TODO: из протокола: Возможны значения от -90 до +90. (макс. отрицательный угол: -45 градусов кодируется
            # 0xA6, макс. положительный угол: 45 градусов кодируется 0x5A, НУЖНО ДЕЛИТЬ ПО ПОЛАМ ПОЛУЧЕННЫЙ УГОЛ
            track['azimuth'] = round(self.__convert(packet[next(index)], 1) / 2, 1)
            # Вычислим радиальную скорость. Она представлена 2мя байтами. 1й - старшая часть, 2й - младшая часть
            track['radSpeed'] = self.__convert(((packet[next(index)] << 8) + packet[next(index)]), 2)
            # Вычислим тангенциальную скорость. Она представлена 2мя байтами. 1й - старшая часть, 2й - младшая часть
            track['tanSpeed'] = self.__convert(((packet[next(index)] << 8) + packet[next(index)]), 2)
            track['sector'] = packet[next(index)]
            trackName = f'track{trackId}'
            trajectoriesData[trackName] = track
        # отправим событие с полученными данными об обнаруженных траекториях
        self.eventsManager.discoveredTrajectories(trajectoriesData)

    def __parseTargetCaptureStateDisplayPacket(self, packet):
        """
        Метод для парсинга пакета отображения статуса захвата цели
        :param packet:
        :return:
        """
        # пакет 3.8, 0x0D - команда статуса захвата трека
        logging.info('Received Capture target packet')
        # print('0x0D - команда статуса захвата трека')
        state = {}
        state['trackId'] = (packet[9] << 8) + packet[10]
        state['setCapture'] = packet[11]
        self.eventsManager.targetCaptureState(state)

    def __parseServerStatePacket(self, packet):
        """
        Метод для парсинга пакета отображения статуса сервера
            'connectionCORT' = 1  # Соединение с КОРТ. 0 - Норма, 1 - Неисправность
            'connectionRLS' = 1  # Сединение с РЛС. 0 - Норма, 1 - Неисправность
            'eradiationFrequency' = 0  # Частота излучения в МГц
            'connectionPTZ' = 1  # Соединение с PTZ (повор-е устр-во). 0 - Норма, 1 - Неисправность
            'activeInterference' = 0  # Активная помеха. 0 - нет, 1 - есть
            'eradiationRLS' = 0  # Излучение РЛС. 0 - выключено, 1 - включено
            'filters' = 0  # Фильтры. 0 - выключены, 1 - включены
            'masks' = 0  # Маски. 0 - выключены, 1 - включены
            'panPTZ' = 0  # Значение PAN PTZ (поворотн-го устр-ва) в шагах ПУ
            'tiltPTZ' = 0  # Значение TILT PTZ (поворотн-го устр-ва) в шагах ПУ
            'controlInterceptedPTZ' = 0  # Управление PTZ (поворотн-го устр-ва) перехвачено. 0 - нет, 1 - да
            'trajectoryCaptured' # Траектория захвачена. 0 - нет, 1 - да
            'autoCapture' = 0  # Автозахват включен. 0 - нет, 1 - да
            'rlsType' = [0,1,2] # Тип РЛС определяется по коду
        """
        # пакет 3.14, 0x14 - команда статуса сервера
        state = {}
        if packet is None:
            # если вместо пакета получено None, значит нет подключения к серверу API Umirs. Для запуска алгоритма
            # обработки такой ситуации необходимо отравить пустой dict
            self.eventsManager.changeRadescanEquipmentState(state)
            return
        state['connectionCORT'] = packet[9]
        state['connectionRLS'] = packet[10]
        state['connectionPTZ'] = packet[11]
        state['activeInterference'] = packet[13]
        state['eradiationRLS'] = packet[14]
        state['filters'] = packet[15]
        state['masks'] = packet[16]
        state['panPTZ'] = (packet[17] << 8) + packet[18]
        state['tiltPTZ'] = (packet[19] << 8) + packet[20]
        state['controlInterceptedPTZ'] = packet[21]
        state['trajectoryCaptured'] = packet[22]
        state['autoCapture'] = packet[23]
        # в зависимости от типа РЛС получим частоту излучения
        state['rlsType'] = self.__getRLSTypeByCode(packet[24])
        state['eradiationFrequency'] = self.__getErFrequencyByTypeRLS(state['rlsType'], packet[12])
        logging.info('Received Ping Packet')

        # в режиме debug принтуем полученный массив байт от Umirs и наш пропарсенный пакет пинга
        logging.debug('Received byte packet{}'.format(packet))
        logging.debug('Parsed packet: {}'.format(state))

        self.eventsManager.changeRadescanEquipmentState(state)

    def __getRLSTypeByCode(self, rlsCode):
        """
        Метод для получения типа РЛС по коду
        :param rlsCode:
        :return:
        """
        rlsType = None
        if rlsCode == 0:
            rlsType = 'RLS2.4'
        elif rlsCode == 1:
            rlsType = 'RLS2.4M'
        elif rlsCode == 2:
            rlsType = 'RLSX'
        return rlsType

    def __getErFrequencyByTypeRLS(self, rlsType, eradiationFrequencyCode):
        """
        Метод для определения частоты излучения по коду, в зависимости от типа РЛС
        :param rlsType: тип РЛС
        :param eradiationFrequencyCode: код частоты
        :return: eradiationFrequency частота излучения РЛС в МГц
        """
        eradiationFrequency = None
        rlsFreqList = []
        if rlsType == 'RLS2.4':
            # РЛС RLS2.4 поддерживает частоты от 2325 до 2475 МГц с интервалом в 50 МГц
            temp = 2275
            while temp <= 2425:
                temp += 50
                rlsFreqList.append(temp)

            try:
                eradiationFrequency = rlsFreqList[eradiationFrequencyCode]
            except IndexError:
                return eradiationFrequency

        elif rlsType == 'RLS2.4M':
            # РЛС RLS2.4М поддерживает частоты от 2312.5 до 2487.5 МГц с интервалом в 12.5 МГц
            temp = 2300
            while temp <= 2475:
                temp += 12.5
                rlsFreqList.append(temp)
            try:
                eradiationFrequency = rlsFreqList[eradiationFrequencyCode]
            except IndexError:
                return eradiationFrequency

        elif rlsType == 'RLSX':
            # РЛС RLSX поддерживает частоты от 9235 до 9760 МГц с интервалом в 35 МГц
            temp = 9200
            while temp <= 9725:
                temp += 35
                rlsFreqList.append(temp)
            try:
                eradiationFrequency = rlsFreqList[eradiationFrequencyCode]
            except IndexError:
                return eradiationFrequency

        return eradiationFrequency

    def __parseServerExtentedStatePacket(self, packet):
        """
        Метод для парсинга пакета отображения расширенного статуса сервера
        :param packet:
        :return:
        """
        # пакет 3.15, 0x15 - команда расширенного статуса сервера (пока нигде не используется)
        state = {}
        state['transmitterRLSState'] = packet[9]
        state['digitalReceiverRLSState'] = packet[10]
        state['analogReceiverRLSState'] = packet[11]
        state['clientCount'] = packet[12]
        state['firstZonePassiveInterference'] = packet[13]
        state['secondZonePassiveInterference'] = packet[14]
        state['thirdZonePassiveInterference'] = packet[15]
        state['fourthZonePassiveInterference'] = packet[16]
        state['sensivityReceiverRLS'] = packet[17]
        state['txRDS1'] = packet[18]
        state['rxRDS1'] = packet[19]
        state['errorsRDS1'] = packet[20]

    def __convert(self, num, len):
        """
        Метод для конвертирования чисел представленных в дополнительном коде
        :param num: число, которое необходимо декодировать
        :param len: сколько байт занимает представление числа num
        :return:
        """
        sign = 0b10000000 if len == 1 else 0b1000000000000000
        bitMask = 0b11111111 if len == 1 else 0b1111111111111111

        # если в старшем разряде нет 1 (этот разряд представляет знак числа), то число положительное, и просто
        # возвращаем это же число
        if num & sign == 0:
            return num
        # иначе, инвертируем число и выравниваем по битовой маске
        else:
            num = ~num & bitMask
            return -1 * (num + 1)

    def __byteIndex(self):
        """
        Метод генерации индексов для перемещения по байтовому массиву, чтобы извлекать данные закодированных траекторий
        :return: index | int - следущий индекс по порядку, начиная с 9го
        """
        index = 9  # с 9го индекса начинается кодирование траекторий
        maxIndex = 417   # согласно протоколу макс. кол-во траекторий = 32, по 13 байтов на одну траекторию = 416 байт
        while index < maxIndex:
            index += 1
            yield index

    def getCurrentPingThread(self):
        return self.__ping

    def _stopThreads(self):
        """
        Служебный метод, необходим для корректного выполнения тестов. Он останавливает потоки self.__live = False, тем
         самым обеспечивая выход из методов, где используются бесконечные циклы
        :return:
        """
        self.__ping.is_stopped = True
        self.__parsePacket.is_stopped = True
        self.__live = False
