def bytearrayBitsToIntBigEndian(bytesArray, firstValidBitIdx, lastvalidBitIdx):
    #print(convertByteArrayToHexString(bytesArray))
    bigInt = int.from_bytes(bytesArray, "big")
    #print(hex(bigInt))
    numValidBits = (lastvalidBitIdx-firstValidBitIdx) + 1
    shiftedBits = (bigInt>>(len(bytesArray) * 8 - (lastvalidBitIdx + 1)))
    #print(hex(shiftedBits))
    bitmask = (2**(numValidBits)-1)
    #print(hex(bitmask))
    return shiftedBits & bitmask

def bytearrayBitsToIntLittleEndian(bytesArray, firstValidBitIdx, lastvalidBitIdx):
    #print(convertByteArrayToHexString(bytesArray))
    bigInt = int.from_bytes(bytesArray, "little")
    #print(hex(bigInt))
    numValidBits = (lastvalidBitIdx-firstValidBitIdx) + 1
    shiftedBits = (bigInt>>(len(bytesArray) * 8 - (lastvalidBitIdx + 1)))
    #print(hex(shiftedBits))
    bitmask = (2**(numValidBits)-1)
    #print(hex(bitmask))
    return shiftedBits & bitmask
