from math import e
import socket
import time
import random
from threading import Thread,Semaphore
import pathlib
from Crypto.Cipher import AES

localIP     = "127.0.0.1"
localPort   = 20001 #puerto servidor local default para el tftp
bufferSize  = 1024

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

semaforo = Semaphore(1)

pathlib.Path('recibido').mkdir(parents=True, exist_ok=True)
pathlib.Path('enviado').mkdir(parents=True, exist_ok=True) 

# Create a datagram socket
UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
# Bind to address and ip
UDPServerSocket.bind((localIP, localPort))
print(bcolors.OKGREEN + "Link Available" + bcolors.ENDC)



## DICCIONARIO DE HASTA N CLIENTES SIMULTANEOS 
buffer = {}   #{"address":"buffer"}
#MENSAJE FINAL X CLIENTE
mensajes = {"cliente":"mensaje"}

tid = 0

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


fileName = ""
pkg = ""
opCode = -1
saddress = -1
error = False
puerto = -1
ix = -1

# A LA ESCUCCHA DE UN WRQ O UN RRQ
while(True):
    ###############################
    # se recibe el mensaje mediante el socket, pero aun no se determina si el "servidor" lo recibe
    bytesAddressPair = UDPServerSocket.recvfrom(bufferSize)
    message = bytesAddressPair[0]
    address = bytesAddressPair[1]
    ###############################
    #print(address)
    print(bcolors.WARNING + "Link bussy" + bcolors.ENDC)
    ###############################
    time.sleep(0.5)
    ack = 5
    ###############################
    if True:
        clientMsg = message.decode("utf-8") #utf-8 o ISO-8859-1
        #print(clientMsg)
        if clientMsg[0] == '2':
            ix = len(clientMsg) - 2
        elif clientMsg[0] == '1':
            ix = len(clientMsg) - 8 #aqui es diferente porque se le suma el puerto
        clientMsg = clientMsg.lower()
        #debemos obtener nombre archivo
        ri = clientMsg.find("netascii")
        if ri < 0 :
            ri = clientMsg.find("octect")
            if ri < 0:
                ri = clientMsg.find("mail")
        fileName = clientMsg[1:ri-1]
        #print(fileName)
        saddress = clientMsg[ix] #el TID del cliente
        if not saddress in buffer:
            buffer[saddress] = ""
        ################################
        #DETECCION DE DUPLICADOS
        if clientMsg == buffer[saddress]:
            print(bcolors.FAIL + "DUPLICADO DETECTADO" + bcolors.ENDC) #enviamos nuevamente una confirmacion en caso de que se haya perdido el ack y se desecha el paquete
        else:
            buffer[saddress] = clientMsg    #guardamos el paquete de ese cliente en el diccionario del buffer
            #print(clientMsg[3])
            if clientMsg[0] == '1' :
                opCode = 1
                puerto = int(clientMsg[len(clientMsg)-6:len(clientMsg)-1]) #leemos el nuevo puerto de comunicacion y el ack sera un paquete DATA
                tid = int(saddress)
                try: #chequeamos si el archivo existe en el servidor antes de enviarlo
                    f = open(fileName,'r') 
                    f.close()
                    break
                except FileNotFoundError:
                    #CODIGO ERROR TFTP 1
                    msgError = "ARCHIVO NO EXISTE"
                    print(bcolors.FAIL + "Server " + str(id) + " recibio ERROR, ERROR SERVIDOR: " + msgError + "FIN DE CONEXION" + bcolors.ENDC) 
                    pkg = "5".encode() + "1".encode() + msgError.encode() + "0".encode() #ERROR PKG
                    error = True
            elif clientMsg[0] == '2' :
                #enviamos ack con block 0
                opCode = 2
                #print(opCode)
                puerto = random.randint(20002, 20100) #generamos un nuevo puerto para descongestionar 
                try: #CHEQUEAMOS SI EL ARCHIVO EXISTE YA EN EL SERVIDOR O NO
                    f = open("enviado/" + fileName,'x') 
                    f.close()
                    pkg = "6".encode() + '0'.encode() + '0'.encode() + str(puerto).encode() + '0'.encode() #ACK PKG
                except FileExistsError : #FileNotFoundError
                    #CODIGO ERROR TFTP 6
                    msgError = "ARCHIVO YA EXISTE"
                    print(msgError)
                    pkg = "5".encode() + "6".encode() + msgError.encode() + "0".encode() #ERROR PKG
            elif clientMsg[0] == '3' :
                #error 4, operacion tftp invalida
                opCode = 3
                pkg = "5".encode() + "4".encode() + "Se esperaba un WWQ o un RRQ (se recibio un DATA)".encode() + "0".encode() #ERROR PKG
            elif clientMsg[0] == '4' :
                #error 4, operacion tftp invalida
                opCode = 4
                pkg = "5".encode() + "4".encode() + "Se esperaba un WWQ o un RRQ (se recibio un ACK)".encode() + "0".encode() #ERROR PKG
            elif clientMsg[0] == '5' :
                #error 4, operacion tftp invalida
                opCode = 5
                msgError = "Se esperaba un WWQ o un RRQ (se recibio un ERROR)"
                pkg = "5".encode() + "4".encode() + msgError.encode() + "0".encode() #ERROR PKG
            else:
                #error 4, operacion tftp invalida
                opCode = 6
                pkg = "5".encode() + "4".encode() + "Se esperaba un WWQ o un RRQ (se recibio un ACKWRQ)".encode() + "0".encode() #ERROR PKG
        time.sleep(0.2)
        # Se envia el ack correspondiente
        UDPServerSocket.sendto(pkg, address) #UDPServerSocket.sendto(bytesToSend, address)
    #print(bcolors.OKGREEN + "Link Available" + bcolors.ENDC)
    break

def sendDATA(id, udpcsocket, blockn, msg, sap, bfsz, pk, err, key): #region critica, aqui se realiza la comunicacion con el servidor
    while True:
        try:  ## SI ES CORRUPTO Y NO LLEGA ACK O EL ACK NO LLEGA A TIEMPO O EL ACK NO COINCIDE CON EL ESPERADO -> OCURRE UN TIMEOUT Y SE REENVIA EL PAQUETE
            if not err:
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
                    msg2 = "ACK: " + msgFromServer[0].decode("utf-8") #se decodifica
                    print(msg2) #se imprime la confirmacion en el bash
                    if int(msg2[5]) == 4 and int(msg2[6:9]) == blockn: #mientras no se reciba el ack correcto, se seguira en escucha hasta que ocurra un timeout, en caso contrario se sale del loop
                        break
                    elif int(msg2[5]) == 5:
                        print(bcolors.FAIL + "Cliente " + str(id) + " recibio ERROR, ERROR SERVIDOR: " + msg2[5:] + " FIN DE CONEXION" + bcolors.ENDC) 
                        break
                    print(bcolors.FAIL + "Server " + str(id) + " recibio ACK Incorrecto" + bcolors.ENDC)
            else:
                udpcsocket.sendto(pk, sap)
        except socket.timeout:
            print(bcolors.FAIL + "Server " + str(id) + " Sin confirmación de ACK, reenviando DATA [Timeout 2s]" + bcolors.ENDC) # si no hay confirmacion imprimimos el error en el bash
            continue #si pasan los 2000ms se reenvia de nuevo el mensaje -> vuelve al try
        else:
            print(bcolors.OKGREEN + "Server " + str(id) + " DATA enviado!" + bcolors.ENDC)
            break #si ahora llega la confirmacion no entra al except y tiene el index correcto -> pasamos al siguiente caracter

def chunkstring(string, length):
    return (string[0+i:length+i] for i in range(0, len(string), length))


finalBlock = False
##OPERACION PARA EL WRQ
if opCode == 2:
    #GENERAMOS LA KEY PARA DESCIFRAR LOS DATA PKG
    key = gen_key(int(saddress), puerto)
    #A LA ESCUCHA DE LOS PAQUETES DE DATA
    localPort = puerto #se cambia de puerto para descongestionar otro IMPLEMENTAR CON CONCURRENCIA U OTRO DESPUES PORQUE DE TODAS FORMAS SE ESTA MATANDO EL PUERTO DE ESCUCHA DE LOS WRQ
    UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    UDPServerSocket.bind((localIP, localPort))
    UDPServerSocket.settimeout(3)#tiempo de gracia (3 segundos) para terminar conexion, en caso de que el ack final se haya perdido
    print(bcolors.OKGREEN + "Link Available" + bcolors.ENDC)
    while(True):
        ack = 5
        try:
            #########################################
            bytesAddressPair = UDPServerSocket.recvfrom(bufferSize)
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
            #SI NO HAY BUFFER PREVIO PARA UN CLIENTE, SE AGREGA AL DICCIONARIO
            ix = len(clientMsg) - 2 #1 a 9 clientes simultaneos
            saddress = clientMsg[ix]
            if not saddress in buffer:
                buffer[saddress] = ""
            ################################
            #DETECCION DE DUPLICADOS
            if clientMsg == buffer[saddress]:
                print(bcolors.FAIL + "DUPLICADO DETECTADO" + bcolors.ENDC) #enviamos nuevamente una confirmacion en caso de que se haya perdido el ack y se desecha el paquete
                ack = clientMsg[1:4] #redundante?
                ##HAY QUE ENVIAR UN MENSAJE DE ERROR SEGUN EL PROTOCOLO
            else:
                buffer[saddress] = clientMsg    #guardamos el paquete de ese cliente en el diccionario del buffer
                #print(clientMsg[3])
                if clientMsg[0] == '1':
                    #error 4, operacion tftp invalida
                    pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un RRQ)".encode() + "0".encode() #ERROR PKG
                elif clientMsg[0] == '2':
                    #error 4, operacion tftp invalida
                    pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un WRQ)".encode() + "0".encode() #ERROR PKG
                elif clientMsg[0] == '3':
                    ack = clientMsg[1:4]
                    pkg = "4".encode() + ack.encode()#str.encode(ack)
                    if not saddress in mensajes:
                        mensajes[saddress] = clientMsg[4:ix-1]
                    else:
                        mensajes[saddress] = mensajes[saddress] + clientMsg[4:ix-1] #vamos guardando el mensaje
                elif clientMsg[0] == '4':
                    #error 4, operacion tftp invalida
                    opCode = 4
                    pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un ACK)".encode() + "0".encode() #ERROR PKG
                elif clientMsg[0] == '5':
                    #error 4, operacion tftp invalida
                    opCode = 5
                    msgError = "Se esperaba un DATA pkg (se recibio un ERROR)"
                    pkg = "5".encode() + "4".encode() + msgError.encode() + "0".encode() #ERROR PKG
                    break
                else:
                    #error 4, operacion tftp invalida
                    opCode = 6
                    pkg = "5".encode() + "4".encode() + "Se esperaba un DATA pkg (se recibio un ACKWRQ)".encode() + "0".encode() #ERROR PKG
                    #print(mensajes)
                    #print(buffer)
            #########################################
            time.sleep(0.2)
            # Se envia el ack correspondiente
            UDPServerSocket.sendto(pkg, address)
        except socket.timeout:
            #SE GUARDA EL ARCHIVO
            if finalBlock:
                print(bcolors.OKGREEN + "Archivo enviado por Cliente Recibido - Fin de Conexion!" + bcolors.ENDC)
                f = open('enviado/' + fileName,'a+')
                f.write(mensajes[saddress])
                f.close()
            else:
                print(bcolors.FAIL + "ERROR TIMED OUT - Fin de Conexion!" + bcolors.ENDC)
            break
        ###########################################################
        print(bcolors.OKGREEN + "Link Available" + bcolors.ENDC)
        ###########################################################
###OPERACION PARA EL RRQ

elif opCode == 1:
    #GENERAMOS LA KEY PARA ENCRIPTAR LOS DATA PKG
    e_key = gen_key(tid, puerto)
    AddressPort   = ("127.0.0.1", puerto)
    nombre_archivo = fileName
    sub =["1"]
    if not error:
        with open(nombre_archivo, encoding = 'utf-8') as f: #ISO-8859-1 utf8
            contents = f.read()
        #DIVISION EN 512Bytes
        brray = contents.encode()
        sub = list(chunkstring(brray, 512)) #ARCHIVO A ENVIAR CODIFICADO EN BYTES Y SUBDIVIDO EN CHUNKS DE 512 BYTES
    block = 1
    id = 0
    for i in sub: #recorremos el mensaje subdividido a enviar elemento por elemento
        print("Server Esta Intentando enviar archivo\n")
        semaforo.acquire()
        sendDATA(id, UDPServerSocket, block, i, AddressPort, bufferSize, pkg, error, e_key)
        semaforo.release()
        block += 1
    print(bcolors.OKGREEN + "Archivo solicitado enviado por Server - Fin de Conexion!" + bcolors.ENDC)
###OPERACION EN CASO DE ERROR
elif opCode == 5:
    print(bcolors.FAIL + "Server " + str(id) + " recibio ERROR, ERROR SERVIDOR: " + clientMsg + "FIN DE CONEXION" + bcolors.ENDC) 

