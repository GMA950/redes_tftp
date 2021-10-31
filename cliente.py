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
modo = 'rrq' #'wrq'#'rrq'
netmode = "netascii"
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
'''
                   TFTP Formats

   Type   Op #     Format without header

          2 bytes    string   1 byte     string   1 byte
          -----------------------------------------------
   RRQ/  | 01/02 |  Filename  |   0  |    Mode    |   0  |
   WRQ    -----------------------------------------------
          2 bytes    2 bytes       n bytes
          ---------------------------------
   DATA  | 03    |   Block #  |    Data    |
          ---------------------------------
          2 bytes    2 bytes
          -------------------
   ACK   | 04    |   Block #  |
          --------------------
          2 bytes  2 bytes        string    1 byte
          ----------------------------------------
   ERROR | 05    |  ErrorCode |   ErrMsg   |   0  |
          ----------------------------------------

Data dentro del paquete DATA tiene un maximo de 512 Bytes

'''

#############################################################################################################################
#SELECCION DEL ARCHIVO Y DIVISION EN 512 BYTES
pathlib.Path('recibido').mkdir(parents=True, exist_ok=True)
pathlib.Path('enviado').mkdir(parents=True, exist_ok=True) 

#############################################################################################################################
#MEJORA DE ENCRIPTACION
def gen_key(key):
    obj = AES.new('eyk_hcua120'+key, AES.MODE_CBC, '16BYTES--IV'+key)
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
            #ENCRIPTAMOS EL PAQUETE DATA ANTES DE ENVIARLO
            #EL PAQUETE TIENE QUE TENER UN LARGO MULTIPLO DE 16 BYTES, POR LO QUE AJUSTAMOS ESO
            data_ = msg
            n = len(data_)
            n_1 = 0
            #print(n)
            pad = ''
            if n < 512: #si el chunk de informacion a encriptar no tiene un largo multiplo de 16 bytes, tenemos que hacerle padding
                while (n+n_1) % 16 != 0: #padding
                    n_1+=1
                for x in range(n_1):
                    pad = pad + ' ' #se le agregan espacios al final
                data_ = data_ + pad.encode()
            #cuando hay 512 bytes en data, el paquete queda de 516 bytes en total
            encriptedData = encriptar(data_, key)
            Data = (3).to_bytes(2,'little') + (blockn).to_bytes(2,'little') + encriptedData
            udpcsocket.sendto(Data, sap)
            while True:
                msgFromServer = udpcsocket.recvfrom(bfsz) # se recibe la confirmacion del mensaje
                recvpkt = msgFromServer[0]
                code = int.from_bytes(recvpkt[0:2], 'little')
                if code == 4: #mientras no se reciba el ack correcto, se seguira en escucha hasta que ocurra un timeout, en caso contrario se sale del loop
                    msgack = int.from_bytes(recvpkt[2:], 'little')
                    if msgack == blockn:
                        print("ACK WRQ: " + str(msgack)) #se imprime la confirmacion en el bash
                    break
                elif code == 5:
                    errorcode = str(int.from_bytes(recvpkt[2:4], 'little'))
                    errormsg = recvpkt[4:len(recvpkt)-1].decode("utf-8")
                    print(bcolors.FAIL + "Cliente " + str(id) + " recibio ERROR, ERROR SERVIDOR: CODE=" + errorcode + " " + errormsg + " FIN DE CONEXION" + bcolors.ENDC)
                    break
                print(bcolors.FAIL + "Cliente " + str(id) + " recibio ACK Incorrecto" + bcolors.ENDC)
        except socket.timeout:
            print(bcolors.FAIL + "Cliente " + str(id) + " Sin confirmación de ACK, reenviando DATA [Timeout 2s]" + bcolors.ENDC) # si no hay confirmacion imprimimos el error en el bash
            continue #si pasan los 2000ms se reenvia de nuevo el mensaje -> vuelve al try
        else:
            print(bcolors.OKGREEN + "Cliente " + str(id) + " DATA enviado!" + bcolors.ENDC)
            break #si ahora llega la confirmacion no entra al except y tiene el index correcto -> pasamos al siguiente caracter
        
#############################################################################################################################

def sendWRQ(id, udpcsocket, blockn, sap, bfsz, fileName, net_mode):
    while True:
        try:
            wrqpkg = (2).to_bytes(2,'little') + fileName.encode() + (0).to_bytes(1,'little') + net_mode.encode() + (0).to_bytes(1,'little')
            udpcsocket.sendto(wrqpkg, sap) #se envia el wrqpkg
            while True:
                msgFromServer = udpcsocket.recvfrom(bfsz) # se recibe la confirmacion del mensaje
                recvpkt = msgFromServer[0]
                code = int.from_bytes(recvpkt[0:2], 'little')
                addresss = msgFromServer[1]
                if code == 4: #mientras no se reciba el ack correcto (opcode = 6, y bloque correcto), se seguira en escucha hasta que ocurra un timeout, en caso contrario se sale del loop
                    ack = int.from_bytes(recvpkt[2:], 'little')
                    if ack == blockn:
                        print("ACK WRQ: " + str(ack)) #se imprime la confirmacion en el bash
                        port = addresss[1]
                    #print(port)
                    break
                elif code == 5: #SI LLEGA UN ERROR SE TERMINA LA CONEXION
                    errorcode = str(int.from_bytes(recvpkt[2:4], 'little'))
                    errormsg = recvpkt[4:len(recvpkt)-1].decode("utf-8")
                    print(bcolors.FAIL + "Cliente " + str(id) + " recibio ERROR, ERROR SERVIDOR: CODE=" + errorcode + " " + errormsg + " FIN DE CONEXION" + bcolors.ENDC)
                    exit()
                print(bcolors.FAIL + "Cliente " + str(id) + " recibio ACK del WRQ Incorrecto" + bcolors.ENDC)
        except socket.timeout:
            print(bcolors.FAIL + "Cliente " + str(id) + " Sin confirmación del WRQ, reenviando [Timeout 2s]" + bcolors.ENDC) # si no hay confirmacion imprimimos el error en el bash
            continue #si pasan los 2000ms se reenvia de nuevo el mensaje -> vuelve al try
        else:
            print(bcolors.OKGREEN + "Cliente " + str(id) + " WRQ enviado!" + bcolors.ENDC)
            break #si ahora llega la confirmacion no entra al except y tiene el index correcto -> pasamos al siguiente caracter
    return port

def sendRRQ(udpcsocket, sap, fileName, net_mode):
    rrqpkg = (1).to_bytes(2,'little') + fileName.encode() + (0).to_bytes(1,'little') + net_mode.encode() + (0).to_bytes(1,'little')
    udpcsocket.sendto(rrqpkg, sap) #se envia el wrqpkg
    


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

            #SE MANDA EL WRQ Y SE RECIBE EL NUEVO PUERTO PARA NO CONGESTIONAR EL PUERTO TFTP
            print("Cliente " + str(self.id) + " Esta Intentando enviar WRQ para archivo: " + nombre_archivo)
            port = sendWRQ(self.id, UDPClientSocket, block, serverAddressPort, bufferSize, nombre_archivo, netmode)
            block += 1
            serverAddressPort   = ("127.0.0.1", port)
            UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
             #######################################################################################################################
            #DIVISION EN 512Bytes
            #print(contents)
            brray = contents.encode() #PASAMOS EL TEXTO EN UTF8 A BYTE ARRAY
            sub = list(chunkstring(brray, 512)) #ARCHIVO A ENVIAR CODIFICADO EN BYTES Y SUBDIVIDO EN CHUNKS DE 512 BYTES
            key = gen_key(str(port)) #KEY PARA ENCRIPTAR GENERADA USANDO EL TID Y EL PUERTO COMO PASSWORDS Y VECTORES DE INICIALIZACION
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
            sendRRQ(UDPClientSocket, serverAddressPort, nombre_archivo, netmode)
            UDPClientSocket.settimeout(3) #tiempo de gracia (3 segundos) para terminar conexion, en caso de que el ack final se haya perdido o no llegue DATA despues de enviar el RRQ
            ack = 0
            key = 0
            while True:
                time.sleep(0.5)
                try:
                    #########################################
                    bytesAddressPair = UDPClientSocket.recvfrom(bufferSize)
                    serverMsg = bytesAddressPair[0]
                    address = bytesAddressPair[1]
                    #########################################
                    print(bcolors.WARNING + "Link bussy" + bcolors.ENDC)
                    time.sleep(0.5)
                    #########################################
                    #print(len(message)) #LOS PAQUETES QUE LLEGAN SON DE 516 BYTES
                    tid = str(address[1])
                    if not tid in buffer:
                        buffer[tid] = ""
                    if ack == 0:
                        key = gen_key(tid) #generamos key para descifrar lo pedido al servidor
                    if len(serverMsg) < 516:
                        finalBlock = True
                    #print(clientMsg)  
                    ################################
                    opCode = int.from_bytes(serverMsg[0:2], 'little')
                    if opCode == 1:
                        #error 4, operacion tftp invalida
                        msgError = "Se esperaba un DATA pkg (se recibio un RRQ)"
                        pkg = (5).to_bytes(2, 'little') + (4).to_bytes(2, 'little') + msgError.encode() + (0).to_bytes(1, 'little') #ERROR PKG
                    elif opCode == 2:
                        #error 4, operacion tftp invalida
                        msgError = "Se esperaba un DATA pkg (se recibio un WRQ)"
                        pkg = (5).to_bytes(2, 'little') + (4).to_bytes(2, 'little') + msgError.encode() + (0).to_bytes(1, 'little') #ERROR PKG
                    elif opCode == 3:
                        ack = int.from_bytes(serverMsg[2:4], 'little')#clientMsg[1:4]
                        #DESENCRIPTAMOS EL MENSAJE
                        msg = desencriptar(serverMsg[4:], key).decode('utf-8')
                        #LE QUITAMOS EL PADDING
                        while msg[-1] == ' ':
                            msg = msg[:-1]
                        #DETECCION DE DUPLICADOS
                        #print(msg)
                        if msg == buffer[tid]:
                            print(bcolors.FAIL + "DUPLICADO DETECTADO" + bcolors.ENDC) #enviamos nuevamente una confirmacion en caso de que se haya perdido el ack y se desecha el paquete
                        else:
                            buffer[tid] = serverMsg    #guardamos el paquete del servidor en el diccionario del buffer
                        #print(msg)
                        pkg = (4).to_bytes(2, 'little') + serverMsg[2:4]
                        if not tid in mensajes:
                            mensajes[tid] = msg
                        else:
                            mensajes[tid] = mensajes[tid] + msg #vamos guardando el mensaje
                    elif opCode == 4:
                        #error 4, operacion tftp invalida
                        msgError = "Se esperaba un DATA pkg (se recibio un ACK)"
                        pkg = (5).to_bytes(2, 'little') + (4).to_bytes(2, 'little') + msgError.encode() + (0).to_bytes(1, 'little') #ERROR PKG
                    elif opCode == 5:
                        #error 4, operacion tftp invalida
                        msgError = "Cliente " + str(id) + " recibio ERROR de Servidor"
                        pkg = (5).to_bytes(2, 'little') + (4).to_bytes(2, 'little') + msgError.encode() + (0).to_bytes(1, 'little') #ERROR PKG
                        break
                    time.sleep(0.2)
                    # Se envia el ack correspondiente
                    UDPClientSocket.sendto(pkg, address)
                except socket.timeout:
                    if finalBlock:
                        print(bcolors.OKGREEN + "Archivo Recibido - Fin de Conexion!" + bcolors.ENDC)
                         #SE GUARDA EL ARCHIVO
                        f = open('recibido/' + nombre_archivo,'a+')
                        f.write(mensajes[tid])
                        f.close()
                    else:
                        print(bcolors.OKGREEN + "RRQ SIN RESPUESTA - Fin de Conexion!" + bcolors.ENDC)
                    break
                print(bcolors.OKGREEN + "Link Available" + bcolors.ENDC)

#############################################################################################################################

#inicializacion de clientes

for x in range(n):
    clientes.append(Cliente(x+1))

for c in clientes: 
     c.start()