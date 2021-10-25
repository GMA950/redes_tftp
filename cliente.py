from random import uniform
import random
import socket
import time
from threading import Thread,Semaphore
import os
import pathlib
from Crypto.Cipher import AES

semaforo = Semaphore(1)
clientes= []

n = 1 #NUMERO DE CLIENTES multithreading sin implementar, DEJAR EN 1

################### SETTINGS DE LA COMUNICACION ##################
nombre_archivo = 'napoleon.txt'
modo = 'rrq' #'wrq'#'rrq' # wrq
##################################################################

#512 Bytes

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

##############################
#OPCODES
# 1 RRQ 
# 2 WRQ
# 3 DATA
# 4 ACK
# 5 ERROR
# 6 ACKWRQ
'''
                    2 bytes     2 bytes      n bytes
                   ----------------------------------
                  | Opcode |   Block #  |   Data     |
                   ----------------------------------

                        Figure 5-2: DATA packet

Data dentro del paquete DATA tiene un maximo de 512 Bytes

'''

#############################################################################################################################
#SELECCION DEL ARCHIVO Y DIVISION EN 512 BYTES
pathlib.Path('recibido').mkdir(parents=True, exist_ok=True)
pathlib.Path('enviado').mkdir(parents=True, exist_ok=True) 



#DEFINICION DE PKGS

Filename = nombre_archivo.encode()
Mode = "netascii".encode()
wrqpkg = "2".encode() + Filename + "0".encode() + Mode + "0".encode()
rrqpkg = "1".encode() + Filename + "0".encode() + Mode + "0".encode() # SE LE SUMA EL PUERTO DE CONEXION

#############################################################################################################################
#MEJORA DE ENCRIPTACION
def gen_key(key, initvectoriv):
    key2 = '000'
    if key < 10:
        key2 = '00' + str(key)
    elif key >= 10 and key < 100:
        key2 = '0' + str(key)
    else:
        key2 = str(key)
    obj = AES.new('eyk_hcua1202_'+key2, AES.MODE_CBC, '16BYTES--IV'+str(initvectoriv))
    return obj

def encriptar(message, key):
    #obj = AES.new('This is a key123', AES.MODE_CBC, 'This is an IV456')
    ciphertext = key.encrypt(message)
    return ciphertext

def desencriptar(ciphertext, key):
    message = key.decrypt(ciphertext)
    return message

#############################################################################################################################

def sendDATA(id, udpcsocket, blockn, msg, sap, bfsz, key): #region critica, aqui se realiza la comunicacion con el servidor
    while True:
        try:  ## SI ES CORRUPTO Y NO LLEGA ACK O EL ACK NO LLEGA A TIEMPO O EL ACK NO COINCIDE CON EL ESPERADO -> OCURRE UN TIMEOUT Y SE REENVIA EL PAQUETE
            if blockn < 10:
                blk = '00' + str(blockn)
            elif blockn >= 10 and blockn < 100:
                blk = '0' + str(blockn)
            else:
                blk = str(blockn)
            Data = "3".encode() + blk.encode() + msg + "0".encode() + str(id).encode() + "0".encode() # se modifico el DATA PKG, ahora se envia el id del cliente y una 

            #ENCRIPTAMOS EL PAQUETE DATA ANTES DE ENVIARLO

            #EL PAQUETE TIENE QUE TENER UN LARGO MULTIPLO DE 16 BYTES, POR LO QUE AJUSTAMOS ESO
            #528 ES EL NUMERO BUSCADO
            n = len(Data)
            pad = ""
            if n < 519: #cuando hay 512 bytes en data, el paquete queda de 519 bytes en total
                while n % 16 != 0: #padding
                    n+=1
                #print("n: " + str(n))
                for x in range(n+1):
                    pad = pad + "9"
                Data = Data + pad.encode()
            else:
                Data = Data + "123456789".encode()#se deja el paquete como multiplo de 16
            #print(len(Data))        
            encriptedData = encriptar(Data, key)
            udpcsocket.sendto(encriptedData, sap)
            while True:
                msgFromServer = udpcsocket.recvfrom(bfsz) # se recibe la confirmacion del mensaje
                msg2 = "ACK: " + msgFromServer[0].decode("utf-8") #(format(msgFromServer[0]))[2] #se decodifica
                print(msg2) #se imprime la confirmacion en el bash
                if int(msg2[5]) == 4 and int(msg2[6:9]) == blockn: #mientras no se reciba el ack correcto, se seguira en escucha hasta que ocurra un timeout, en caso contrario se sale del loop
                    break
                elif int(msg2[5]) == 5:
                    print(bcolors.FAIL + "Cliente " + str(id) + " recibio ERROR, ERROR SERVIDOR: " + msg2[5:] + " FIN DE CONEXION" + bcolors.ENDC) 
                    break
                print(bcolors.FAIL + "Cliente " + str(id) + " recibio ACK Incorrecto" + bcolors.ENDC)
        except socket.timeout:
            print(bcolors.FAIL + "Cliente " + str(id) + " Sin confirmación de ACK, reenviando DATA [Timeout 2s]" + bcolors.ENDC) # si no hay confirmacion imprimimos el error en el bash
            continue #si pasan los 2000ms se reenvia de nuevo el mensaje -> vuelve al try
        else:
            print(bcolors.OKGREEN + "Cliente " + str(id) + " DATA enviado!" + bcolors.ENDC)
            break #si ahora llega la confirmacion no entra al except y tiene el index correcto -> pasamos al siguiente caracter
        
#############################################################################################################################

def sendWRQ(id, udpcsocket, blockn, sap, bfsz):
    while True:
        try:
            wrq = wrqpkg + str(id).encode() + "0".encode()
            udpcsocket.sendto(wrq, sap) #se envia el wrqpkg
            while True:
                msgFromServer = udpcsocket.recvfrom(bfsz) # se recibe la confirmacion del mensaje
                msg1 = msgFromServer[0].decode("utf-8")
                msg2 = "ACK WRQ: " + msg1[1] #+(format(msgFromServer[0]))[2] #se decodifica
                print(msg2) #se imprime la confirmacion en el bash
                #print(msg1) #se imprime la confirmacion en el bash
                if int(msg1[0]) == 6 and int(msg1[1]) == blockn: #mientras no se reciba el ack correcto (opcode = 6, y bloque correcto), se seguira en escucha hasta que ocurra un timeout, en caso contrario se sale del loop
                    port = int(msg1[3:8])
                    #print(port)
                    break
                elif int(msg1[0]) == 5: #SI LLEGA UN ERROR SE TERMINA LA CONEXION
                    print(bcolors.FAIL + "Cliente " + str(id) + " recibio ERROR, ERROR SERVIDOR: " + msg1 + " FIN DE CONEXION" + bcolors.ENDC)
                    exit() 
                    break
                print(bcolors.FAIL + "Cliente " + str(id) + " recibio ACK del WRQ Incorrecto" + bcolors.ENDC)
        except socket.timeout:
            print(bcolors.FAIL + "Cliente " + str(id) + " Sin confirmación del WRQ, reenviando [Timeout 2s]" + bcolors.ENDC) # si no hay confirmacion imprimimos el error en el bash
            continue #si pasan los 2000ms se reenvia de nuevo el mensaje -> vuelve al try
        else:
            print(bcolors.OKGREEN + "Cliente " + str(id) + " WRQ enviado!" + bcolors.ENDC)
            break #si ahora llega la confirmacion no entra al except y tiene el index correcto -> pasamos al siguiente caracter
    return port

def sendRRQ(id, udpcsocket, sap):
    port = random.randint(20002, 20100)
    rrq = rrqpkg + str(id).encode() + "0".encode() + str(port).encode() + "0".encode()
    udpcsocket.sendto(rrq, sap) #se envia el wrqpkg
    return port


#############################################################################################################################
buffer = {}   #{"address":"buffer"}
#MENSAJE FINAL X CLIENTE
mensajes = {"cliente":"mensaje"}
def chunkstring(string, length):
    return (string[0+i:length+i] for i in range(0, len(string), length))


class Cliente(Thread):
    def __init__(self,id): #Constructor de la clase
        Thread.__init__(self)
        self.id=id
    def run(self): #Metodo que se ejecutara con la llamada start
        ##########################################################################
        serverAddressPort   = ("127.0.0.1", 20001)
        bufferSize          = 1024
        # Create a UDP socket at client side
        UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        # configuramos un tiempo maximo para timeout de 2000ms
        UDPClientSocket.settimeout(2)
        block = 0
        ########################################################################################################
        #----------------------------------------- OPERACION WRQ ----------------------------------------------#
        ########################################################################################################
        if modo == 'wrq':

            with open(nombre_archivo, encoding = 'utf-8') as f: #ISO-8859-1 utf8
                contents = f.read()
                #print(contents)

            #sizetest = len(contents.encode('utf-8'))

            #SE MANDA EL WRQ Y SE RECIBE EL NUEVO PUERTO PARA NO CONGESTIONAR EL PUERTO TFTP
            print("Cliente " + str(self.id) + " Esta Intentando enviar WRQ para archivo: " + nombre_archivo)
            port = sendWRQ(self.id, UDPClientSocket, block, serverAddressPort, bufferSize)
            block += 1
            serverAddressPort   = ("127.0.0.1", port)
            UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
             #######################################################################################################################
            #DIVISION EN 512Bytes
            #print(contents)
            brray = contents.encode() #PASAMOS EL TEXTO EN UTF8 A BYTE ARRAY
            sub = list(chunkstring(brray, 512)) #ARCHIVO A ENVIAR CODIFICADO EN BYTES Y SUBDIVIDO EN CHUNKS DE 512 BYTES
            key = gen_key(self.id, port) #KEY PARA ENCRIPTAR GENERADA USANDO EL TID Y EL PUERTO COMO PASSWORDS Y VECTORES DE INICIALIZACION
            #######################################################################################################################
            
            for i in sub: #recorremos el mensaje subdividido a enviar elemento por elemento
                print("Cliente " + str(self.id) + " Esta Intentando enviar archivo")
                semaforo.acquire()
                sendDATA(self.id, UDPClientSocket, block, i, serverAddressPort, bufferSize, key)
                semaforo.release()
                block += 1
            print(bcolors.OKGREEN + "Archivo Enviado - Fin de Conexion!" + bcolors.ENDC)
        ########################################################################################################
        #----------------------------------------- OPERACION RRQ ----------------------------------------------#
        ########################################################################################################
        finalBlock = False
        if modo == 'rrq':
            print("Cliente " + str(self.id) + " Esta Intentando enviar RRQ para archivo: " + nombre_archivo)
            port = sendRRQ(self.id, UDPClientSocket, serverAddressPort)
            serverAddressPort   = ("127.0.0.1", port)
            UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            UDPClientSocket.bind(serverAddressPort) #importante
            UDPClientSocket.settimeout(3) #tiempo de gracia (3 segundos) para terminar conexion, en caso de que el ack final se haya perdido o no llegue DATA despues de enviar el RRQ
            ack = -1
            #generamos key para descifrar lo pedido al servidor
            key = gen_key(self.id, port)
            while True:
                time.sleep(0.5)
                try:
                    #########################################
                    bytesAddressPair = UDPClientSocket.recvfrom(bufferSize)
                    message = bytesAddressPair[0]
                    address = bytesAddressPair[1]
                    #########################################
                    print(bcolors.WARNING + "Link bussy" + bcolors.ENDC)
                    time.sleep(0.5)
                    #########################################
                    #print(len(message)) #LOS PAQUETES QUE LLEGAN SON DE 528 BYTES
                    if len(message) < 528:
                        finalBlock = True
                    #DESENCRIPTAMOS EL MENSAJE
                    clientMsg = desencriptar(message, key)
                    #LE QUITAMOS EL PADDING
                    n = len(clientMsg)
                    if n == 528:
                        clientMsg = clientMsg[0:519]
                        clientMsg = clientMsg.decode("utf-8")
                    else:
                        clientMsg = clientMsg.decode("utf-8")
                        while clientMsg[-1] == '9':
                            clientMsg = clientMsg[:-1]
                    #print(clientMsg)  
                    ################################
                    ix = len(clientMsg) - 2
                    saddress = clientMsg[ix]
                    if not saddress in buffer:
                        buffer[saddress] = ""
                    if clientMsg == buffer[saddress]:
                        print(bcolors.FAIL + "DUPLICADO DETECTADO" + bcolors.ENDC) #enviamos nuevamente una confirmacion en caso de que se haya perdido el ack y se desecha el paquete
                        ack = clientMsg[1:4] #redundante?
                        ##HAY QUE ENVIAR UN MENSAJE DE ERROR SEGUN EL PROTOCOLO
                    else:
                        buffer[saddress] = clientMsg    #guardamos el paquete de ese cliente en el diccionario del buffer
                        #print(clientMsg[3])
                        if clientMsg[0] == '1' :
                            #error 4, operacion tftp invalida
                             pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un RRQ)".encode() + "0".encode() #ERROR PKG
                        elif clientMsg[0] == '2' :
                            #error 4, operacion tftp invalida
                            pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un WRQ)".encode() + "0".encode() #ERROR PKG
                        elif clientMsg[0] == '3' :
                            ack = clientMsg[1:4]
                            pkg = "4".encode() + ack.encode()#str.encode(ack)
                            if not saddress in mensajes:
                                mensajes[saddress] = clientMsg[4:ix-1]
                            else:
                                mensajes[saddress] = mensajes[saddress] + clientMsg[4:ix-1] #vamos guardando el mensaje
                        elif clientMsg[0] == '4':
                            #error 4, operacion tftp invalida
                            pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un ACK)".encode() + "0".encode() #ERROR PKG
                        elif clientMsg[0] == '5':
                            #error 4, operacion tftp invalida
                            print(bcolors.FAIL + "Cliente " + str(id) + " recibio ERROR, ERROR SERVIDOR: " + clientMsg + " FIN DE CONEXION" + bcolors.ENDC) 
                            #pkg = "5".encode() + "4".encode + "Se esperaba un DATA pkg (se recibio un ERROR)" + "0".encode #ERROR PKG
                            break
                        else:
                            #error 4, operacion tftp invalida
                            pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un ACKWRQ)".encode() + "0".encode() #ERROR PKG
                    time.sleep(0.2)
                    # Se envia el ack correspondiente
                    UDPClientSocket.sendto(pkg, address)
                except socket.timeout:
                    if finalBlock:
                        print(bcolors.OKGREEN + "Archivo Recibido - Fin de Conexion!" + bcolors.ENDC)
                         #SE GUARDA EL ARCHIVO
                        f = open('recibido/' + nombre_archivo,'a+')
                        f.write(mensajes[saddress])
                        f.close()
                    else:
                        print(bcolors.OKGREEN + "RRQ SIN RESPUESTA - Fin de Conexion!" + bcolors.ENDC)
                    break
                print(bcolors.OKGREEN + "Link Available" + bcolors.ENDC)
                #if finalBlock: #tiempo de gracia (3 segundos) para terminar conexion, en caso de que el ack final se haya perdido
                #    UDPClientSocket.settimeout(3)

#############################################################################################################################

#inicializacion de clientes

for x in range(n):
    clientes.append(Cliente(x+1))

for c in clientes: 
     c.start()