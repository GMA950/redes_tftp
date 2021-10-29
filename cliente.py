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
            if blockn < 10:
                blk = '00' + str(blockn)
            elif blockn >= 10 and blockn < 100:
                blk = '0' + str(blockn)
            else:
                blk = str(blockn)

            Data = "3".encode() + blk.encode() + msg # data pkg

            #ENCRIPTAMOS EL PAQUETE DATA ANTES DE ENVIARLO

            #EL PAQUETE TIENE QUE TENER UN LARGO MULTIPLO DE 16 BYTES, POR LO QUE AJUSTAMOS ESO
            #528 ES EL NUMERO BUSCADO
            n = len(Data)
            n_1 = 0
            #print(n)
            pad = ""
            if n < 516: #cuando hay 512 bytes en data, el paquete queda de 516 bytes en total
                while (n+n_1) % 16 != 0: #padding
                    n_1+=1
                #print("n: " + str(n))
                for x in range(n_1):
                    pad = pad + "9"
                Data = Data + pad.encode()
            else:
                Data = Data + "123456789012".encode()#se deja el paquete como multiplo de 16 al añadirle 12 bytes extras
            #print(len(Data))        
            encriptedData = encriptar(Data, key)
            udpcsocket.sendto(encriptedData, sap)
            while True:
                msgFromServer = udpcsocket.recvfrom(bfsz) # se recibe la confirmacion del mensaje
                msgack = msgFromServer[0].decode("utf-8")
                print("ACK: " + msgack[1:4]) #se imprime la confirmacion en el bash
                if int(msgack[0]) == 4 and int(msgack[1:4]) == blockn: #mientras no se reciba el ack correcto, se seguira en escucha hasta que ocurra un timeout, en caso contrario se sale del loop
                    break
                elif int(msgack[0]) == 5:
                    print(bcolors.FAIL + "Cliente " + str(id) + " recibio ERROR, ERROR SERVIDOR: " + msgack + " FIN DE CONEXION" + bcolors.ENDC) 
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
            wrqpkg = "2".encode() + fileName.encode() + "0".encode() + net_mode.encode() + "0".encode()
            udpcsocket.sendto(wrqpkg, sap) #se envia el wrqpkg
            while True:
                msgFromServer = udpcsocket.recvfrom(bfsz) # se recibe la confirmacion del mensaje
                msg1 = msgFromServer[0].decode("utf-8")
                addresss = msgFromServer[1]
                msg2 = "ACK WRQ: " + msg1[1] #+(format(msgFromServer[0]))[2] #se decodifica
                print(msg2) #se imprime la confirmacion en el bash
                #print(msg1) 
                if int(msg1[0]) == 4 and int(msg1[1]) == blockn: #mientras no se reciba el ack correcto (opcode = 6, y bloque correcto), se seguira en escucha hasta que ocurra un timeout, en caso contrario se sale del loop
                    port = addresss[1]
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

def sendRRQ(udpcsocket, sap, fileName, net_mode):
    #port = random.randint(20002, 20100)
    rrqpkg = "1".encode() + fileName.encode() + "0".encode() + net_mode.encode() + "0".encode() 
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

            #sizetest = len(contents.encode('utf-8'))

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
            ack = ''
            key = ''
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
                    tid = str(address[1])
                    if ack == '':
                        key = gen_key(str(tid)) #generamos key para descifrar lo pedido al servidor
                    if len(message) < 528:
                        finalBlock = True
                    #DESENCRIPTAMOS EL MENSAJE
                    clientMsg = desencriptar(message, key)
                    #LE QUITAMOS EL PADDING
                    n = len(clientMsg)
                    if n == 528:
                        clientMsg = clientMsg[0:516]
                        clientMsg = clientMsg.decode("utf-8")
                    else:
                        clientMsg = clientMsg.decode("utf-8")
                        while clientMsg[-1] == '9':
                            clientMsg = clientMsg[:-1]
                    #print(clientMsg)  
                    ################################
                    if not tid in buffer:
                        buffer[tid] = ""
                    if clientMsg == buffer[tid]:
                        print(bcolors.FAIL + "DUPLICADO DETECTADO" + bcolors.ENDC) #enviamos nuevamente una confirmacion en caso de que se haya perdido el ack y se desecha el paquete
                        ack = clientMsg[1:4] #redundante?
                        ##HAY QUE ENVIAR UN MENSAJE DE ERROR SEGUN EL PROTOCOLO
                    else:
                        buffer[tid] = clientMsg    #guardamos el paquete de ese cliente en el diccionario del buffer
                        #print(clientMsg[3])
                        opCode = int(clientMsg[0])
                        if opCode == 1 :
                            #error 4, operacion tftp invalida
                             pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un RRQ)".encode() + "0".encode() #ERROR PKG
                        elif opCode == 2 :
                            #error 4, operacion tftp invalida
                            pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un WRQ)".encode() + "0".encode() #ERROR PKG
                        elif opCode == 3 :
                            ack = clientMsg[1:4]
                            pkg = "4".encode() + ack.encode()#str.encode(ack)
                            if not tid in mensajes:
                                mensajes[tid] = clientMsg[4:]
                            else:
                                mensajes[tid] = mensajes[tid] + clientMsg[4:] #vamos guardando el mensaje
                        elif opCode == 4:
                            #error 4, operacion tftp invalida
                            pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un ACK)".encode() + "0".encode() #ERROR PKG
                        elif opCode == 5:
                            #error 4, operacion tftp invalida
                            print(bcolors.FAIL + "Cliente " + str(id) + " recibio ERROR, ERROR SERVIDOR: " + clientMsg + " FIN DE CONEXION" + bcolors.ENDC) 
                            #pkg = "5".encode() + "4".encode + "Se esperaba un DATA pkg (se recibio un ERROR)" + "0".encode #ERROR PKG
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