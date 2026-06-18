import sys
import os
import math

def extract_sample(offset):
    print(f'sample {sampleindex:03} at {offset}')
    rom.seek(offset)
    
    samplehasloop = int.from_bytes(rom.read(4), 'little') >> 30
    samplerate = int.from_bytes(rom.read(4), 'little') >> 10
    sampleloop = int.from_bytes(rom.read(4), 'little')
    samplelength = int.from_bytes(rom.read(4), 'little')
    
    samples = rom.read(samplelength)
    
    folder = f'samples_{id.decode()}'
    
    if not os.path.isdir(folder):
        os.makedirs(folder)
    
    with open(f'{folder}\\{sampleindex}.wav', 'wb') as out:
        out.write('RIFF'.encode('ascii'))
        out.write((samplelength + 36 + (68 * samplehasloop)).to_bytes(4, 'little')) # riff size
        out.write('WAVEfmt '.encode('ascii'))
        out.write((16).to_bytes(4, 'little')) # fmt size
        out.write((1).to_bytes(2, 'little')) # type
        out.write((1).to_bytes(2, 'little')) # channels
        out.write((samplerate).to_bytes(4, 'little')) # sample rate
        out.write((samplerate * 1 * 1).to_bytes(4, 'little')) # sample rate * bytes * channels
        out.write((1 * 1).to_bytes(2, 'little')) # bytes * channels
        out.write((8).to_bytes(2, 'little')) # bits
        
        if samplehasloop:
            out.write('smpl'.encode('ascii'))
            out.write((60).to_bytes(4, 'little')) # smpl size
            out.write(b'\x00' * 12)
            out.write((60).to_bytes(4, 'little')) # note
            out.write(b'\x00' * 12)
            out.write((1).to_bytes(4, 'little')) # enable loop
            out.write(b'\x00' * 12)
            out.write((sampleloop).to_bytes(4, 'little')) # loop start
            out.write((samplelength - 1).to_bytes(4, 'little')) # loop end
            out.write(b'\x00' * 8)

        out.write('data'.encode('ascii'))
        out.write((samplelength).to_bytes(4, 'little')) # data size
        out.write(bytes(samples))

def extract_instrument(offset, sections):
    print(f'\ninstrument {instrumentindex} at {offset}')
    rom.seek(offset)
    
    for i in range(sections):
        notelow = int.from_bytes(rom.read(1))
        notehigh = int.from_bytes(rom.read(1))
        sample = int.from_bytes(rom.read(1))
        unpitched = int.from_bytes(rom.read(1)) >> 7
        rom.read(4)
        
        print(f'----range {notelow:03} to {notehigh:03} with sample {sample:03}, unpitched {unpitched}')

def convert_song(offset):
    rom.seek(offset)
    
    trackbits = int.from_bytes(rom.read(2), 'little')
    
    tracksenabled = []
    for i in range(12):
        if trackbits >> i & 1:
            tracksenabled.append(i)
    
    trackoffset = [0] * 12
    for i in tracksenabled:
        trackoffset[i] = int.from_bytes(rom.read(2), 'little')
    
    global mid
    
    folder = f'midi_{id.decode()}'
    
    if not os.path.isdir(folder):
        os.makedirs(folder)
    
    with open(f'{folder}\\{songindex}.mid', 'w+b') as mid:
        mid.write('MThd'.encode())
        mid.write((6).to_bytes(4)) # length of MThd chunk (always 6)
        mid.write((1).to_bytes(2)) # format 1
        mid.write((len(tracksenabled)).to_bytes(2)) # track count
        mid.write((48).to_bytes(2)) # timebase
        
        global mtrk
        mtrk = []
        for i in tracksenabled:
            rom.seek(offset + trackoffset[i])
            
            global finish
            global volume
            global free
            global freenote
            global wait
            finish = 0
            volume = 127
            free = 0
            freenote = 0
            wait = 0
            
            mtrk.append(mid.tell())
            mid.write('MTrk'.encode())
            mid.write((302302).to_bytes(4))
            mid.write(b'\x00')
            
            while not finish:
                song_convert(i)
            
            mid.write(b'\xFF\x2F\x00')
            
        fix_mtrk()

def song_convert(channel):
    global finish
    global volume
    global note
    global free
    global freenote
    global wait
    
    byte = int.from_bytes(rom.read(1))
    
    match byte:
        case 0xF0: # set instrument
            value = int.from_bytes(rom.read(1))
            
            write_wait()
            
            mid.write((0xB0 + channel).to_bytes(1))
            mid.write(b'\x00')
            mid.write((value >> 7).to_bytes(1))
            mid.write(b'\x00')
            
            mid.write((0xC0 + channel).to_bytes(1))
            mid.write((value & 0x7F).to_bytes(1))
            mid.write(b'\x00')
            
        case 0xF1: # volume
            volume = int.from_bytes(rom.read(1))
            volume = round(((volume / 255) ** 0.5) * 127)
            
            write_wait()
            
            mid.write((0xB0 + channel).to_bytes(1))
            mid.write(b'\x07')
            mid.write(volume.to_bytes(1))
            mid.write(b'\x00')
            
        case 0xF2: # pan
            value = 0xFF-int.from_bytes(rom.read(1))
            value = math.ceil(value / 2)
            
            if channel == 8 or channel == 9:
                if value < 0x40:
                    value = 0
                if value > 0x40:
                    value = 0x80
            
            if value > 0x7F:
                value = 0x7F
            
            write_wait()
            
            mid.write((0xB0 + channel).to_bytes(1))
            mid.write(b'\x0A')
            mid.write((value).to_bytes(1))
            mid.write(b'\x00')
        
        case 0xF4: # pitch bend range
            value = int.from_bytes(rom.read(1))
            
            write_wait()
            
            # duno why but it needs these
            mid.write((0xB0 + channel).to_bytes(1))
            mid.write(b'\x65\x00\x00')
            mid.write((0xB0 + channel).to_bytes(1))
            mid.write(b'\x64\x00\x00')
            
            mid.write((0xB0 + channel).to_bytes(1))
            mid.write(b'\x06')
            mid.write((value).to_bytes(1))
            mid.write(b'\x00')
        
        case 0xF5: # pitch bend
            value = int.from_bytes(rom.read(1), signed=True)
            value = value + 128 << 6 # convert to midi
            
            write_wait()
            
            mid.write((0xE0 + channel).to_bytes(1))
            mid.write((value & 0x7F).to_bytes(1))
            mid.write((value >> 7).to_bytes(1))
            mid.write(b'\x00')
            
        case 0xF6: # wait
            wait += int.from_bytes(rom.read(1))
            
        case 0xF8: # jump
            finish = 1
            song_notestop(channel, note)
            
        case 0xF9: # set bpm
            value = int.from_bytes(rom.read(1))
            
            if value < 4:
                return
            
            write_wait()
            
            mid.write(b'\xFF\x51\x03')
            mid.write((round(60000000 / value)).to_bytes(3))
            mid.write(b'\x00')
            
        case 0xFF: # finish
            finish = 1
            
        case _:
            if byte < 0xF0: # note
                readwait = 0
                
                if byte == 0:
                    note = int.from_bytes(rom.read(1))
                    note -= 0x80
                    if note < 0: # duno why this would ever happen but it does in the title screen (41) and this fixes it
                        return
                    readwait += int.from_bytes(rom.read(1))
                else:
                    readwait += byte
                    note = int.from_bytes(rom.read(1))
                
                note %= 0x80
                
                if free and note == freenote:
                    free = 0
                else:
                    if free:
                        song_notestop(channel, freenote)
                        free = 0
                    song_notestart(channel, note)
                
                if byte == 0:
                    free = 1
                    freenote = note
                
                wait += readwait
                
                if not free:
                    song_notestop(channel, note)

def song_notestart(channel, note):
    write_wait()
    
    mid.write((0x90 + channel).to_bytes(1))
    mid.write((note).to_bytes(1))
    mid.write((0x7F).to_bytes(1))
    mid.write(b'\x00')

def song_notestop(channel, note):
    write_wait()
    
    mid.write((0x80 + channel).to_bytes(1))
    mid.write((note).to_bytes(1))
    mid.write((0x7F).to_bytes(1))
    mid.write(b'\x00')

def write_wait():
    global wait
    
    mid.seek(mid.tell() - 1)
    write_7bit(wait)
    wait = 0

def read_7bit():
    value = 0
    read = 0x80
    
    while read >= 0x80:
        read = int.from_bytes(mid.read(1))
        value += read
        
        if read >= 0x80:
            value = value - 0x80 << 7
    
    return value

def write_7bit(value):
    length = 0
    count = value
    while count > 0:
        count = count >> 7
        length += 1
    if length == 0:
        mid.write(b'\x00')
        return
    
    for i in range(length):
        part = (length - 1) - i
        output = value >> (7 * part) & 0x7F
        if part > 0:
            output += 0x80
        mid.write(output.to_bytes(1))

def fix_mtrk():
    global mtrk
    
    mtrk.append(mid.tell())
    
    for i in range(len(mtrk) - 1):
        mid.seek(mtrk[i] + 4)
        temp = mtrk[i + 1] - mtrk[i] - 8
        mid.write(temp.to_bytes(4, 'big'))
    
    mid.seek(0x0A)
    temp = len(mtrk) - 1
    mid.write(temp.to_bytes(2, 'big'))

def extract_song(offset):
    print(f'song {songindex} at {offset}')
    rom.seek(offset)
    
    folder = f'songs_{id.decode()}'
    
    if not os.path.isdir(folder):
        os.makedirs(folder)
    
    with open(f'{folder}\\{songindex}.txt', 'w+') as dump:
        trackbits = int.from_bytes(rom.read(2), 'little')
        
        tracksenabled = []
        for i in range(12):
            if trackbits >> i & 1:
                tracksenabled.append(i)
        
        trackoffset = [0] * 12
        for i in tracksenabled:
            trackoffset[i] = int.from_bytes(rom.read(2), 'little')
        
        linelocation = []
        lineseek = []
        for i in tracksenabled:
            dump.write(f'Track {i}:\n')
            linelocation.append(0)
            lineseek.append(dump.tell())
            rom.seek(offset + trackoffset[i])
            
            tick = 0
            separate = 0
            finish = 0
            while not finish:
                if tick >= separate:
                    separate += 192
                    dump.write(f'\t-------- bar {int(tick / 192) + 1} --------\n')
                    linelocation.append(0)
                    lineseek.append(dump.tell())
                
                linelocation.append(rom.tell())
                lineseek.append(dump.tell())
                byte = int.from_bytes(rom.read(1))
                
                match byte:
                    case 0xF0:
                        value = int.from_bytes(rom.read(1))
                        dump.write(f'\tInstrument {value}\n')
                        
                    case 0xF1:
                        value = int.from_bytes(rom.read(1))
                        dump.write(f'\tVolume {value}\n')
                        
                    case 0xF2:
                        value = int.from_bytes(rom.read(1)) - 0x80
                        dump.write(f'\tPan {value}\n')
                        
                    case 0xF4:
                        value = int.from_bytes(rom.read(1))
                        dump.write(f'\tRange {value}\n')
                        
                    case 0xF5:
                        value = int.from_bytes(rom.read(1), signed=True)
                        dump.write(f'\tBend {value}\n')
                        
                    case 0xF6:
                        value = int.from_bytes(rom.read(1))
                        tick += value
                        dump.write(f'\tWait {value}\n')
                        
                    case 0xF8:
                        finish = 1
                        value = int.from_bytes(rom.read(2), 'little', signed=True)
                        dump.write(f'\tJump\n')
                        jump = linelocation.index(rom.tell() + value)
                        dump.seek(lineseek[jump])
                        temp = dump.read()
                        dump.seek(lineseek[jump])
                        dump.write(f'Loop {i}:\n')
                        dump.write(temp)
                        
                    case 0xF9:
                        value = int.from_bytes(rom.read(1))
                        dump.write(f'\tBPM {value}\n')
                        
                    case 0xFF:
                        finish = 1
                        dump.write(f'\tEnd\n')
                        
                    case _:
                        if byte < 0xF0:
                            if byte == 0:
                                value = int.from_bytes(rom.read(1)) - 0x80
                                if value >= 0:
                                    value2 = int.from_bytes(rom.read(1))
                                    tick += value2
                                    dump.write(f'\tExtend {note_name(value)} {value2}\n')
                                else:
                                    dump.write(f'\tExtended {value + 0x80}\n')
                            else:
                                value = int.from_bytes(rom.read(1))
                                tick += byte
                                dump.write(f'\tNote {note_name(value)} {byte}\n')
                        else:
                            dump.write(f'\tUNKNOWN {byte}\n')
            
            dump.write(f'\n')

def note_name(note):
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return f'{names[note % 12]}{int(note / 12)}'

if len(sys.argv) < 2:
    print("you forgot the rom")
    sys.exit()

global pack
pack = int(input('Unpack/Repack? [0/1]:'))

global tomidi
tomidi = 0
if not pack:
    tomidi = int(input('Convert songs to midi? [0/1]:'))

with open(sys.argv[1], 'rb') as rom:
    rom.seek(0xAC)
    id = rom.read(4)
    
    match id:
        case b'A88E':
            songtable = 0x21CB70
            songcount = 407
            instrumenttable = 0x21D1CC
            instrumentcount = 260
            sampletable = 0xA806B8
            samplecount = 236
        case b'A88J':
            songtable = 0x205060
            songcount = 418
            instrumenttable = 0x2056E8
            instrumentcount = 260
            sampletable = 0x9721A8
            samplecount = 239
        case b'\x00\x00\x00\x00':
            songtable = 0x116BA0
            songcount = 172
            instrumenttable = 0x116E54
            instrumentcount = 260
            sampletable = 0x5C6730
            samplecount = 150
            id = b'DEMO'
    
    # extract songs
    for songindex in range(songcount):
            rom.seek(songtable + (songindex * 4))
            offset = int.from_bytes(rom.read(4), 'little') - 0x08000000
            
            if offset > 0:
                if tomidi: convert_song(offset)