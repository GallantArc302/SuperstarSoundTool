import sys
import os

def extract_sample(offset):
    name = get_name(sampleindex, samplenames)
    
    print(f'sample {name} at {offset}')
    rom.seek(offset)
    
    samplehasloop = int.from_bytes(rom.read(4), 'little') >> 30
    samplerate = int.from_bytes(rom.read(4), 'little') >> 10
    sampleloop = int.from_bytes(rom.read(4), 'little')
    samplelength = int.from_bytes(rom.read(4), 'little')
    
    global header
    if samplehasloop:
        header += f'{name} {sampleloop}\n'
    else:
        header += f'{name}\n'
    
    samples = rom.read(samplelength)
    
    with open(f'{folder}\\{name}.wav', 'wb') as out:
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
    name = get_name(instrumentindex, instrumentnames)
    
    print(f'instrument {name} at {offset}')
    rom.seek(offset)
    
    global header
    header += f'{name}\n'
    
    with open(f'{folder}\\{name}.txt', 'w+') as out:
        for i in range(sections):
            notelow = int.from_bytes(rom.read(1), 'little')
            notehigh = int.from_bytes(rom.read(1), 'little')
            sample = int.from_bytes(rom.read(1), 'little')
            unpitched = int.from_bytes(rom.read(1), 'little') >> 7
            attack = int.from_bytes(rom.read(1), 'little')
            decay = int.from_bytes(rom.read(1), 'little')
            sustain = int.from_bytes(rom.read(1), 'little')
            release = int.from_bytes(rom.read(1), 'little')
            
            if not (instrumentindex >= 190 and instrumentindex <= 199):
                sample = get_name(sample, samplenames)
            
            out.write(f'{notelow:03} {notehigh:03} {sample} {unpitched} {attack:03} {decay:03} {sustain:03} {release:03}\n')

def extract_song(offset):
    name = get_name(songindex, songnames)
    
    print(f'song {name} at {offset}')
    rom.seek(offset)
    
    global header
    header += f'{name}\n'
    
    with open(f'{folder}\\{name}.txt', 'w+') as out:
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
            out.write(f'Track {i}:\n')
            linelocation.append(0)
            lineseek.append(out.tell())
            rom.seek(offset + trackoffset[i])
            
            tick = 0
            separate = 0
            finish = 0
            while not finish:
                if tick >= separate:
                    separate += 192
                    out.write(f'\t-------- bar {int(tick / 192) + 1} --------\n')
                    linelocation.append(0)
                    lineseek.append(out.tell())
                
                linelocation.append(rom.tell())
                lineseek.append(out.tell())
                byte = int.from_bytes(rom.read(1), 'little')
                
                match byte:
                    case 0xF0:
                        value = get_name(int.from_bytes(rom.read(1), 'little'), instrumentnames)
                        out.write(f'\tInstrument {value}\n')
                        
                    case 0xF1:
                        value = int.from_bytes(rom.read(1), 'little')
                        out.write(f'\tVolume {value}\n')
                        
                    case 0xF2:
                        value = 0x80 - int.from_bytes(rom.read(1), 'little')
                        out.write(f'\tPan {value}\n')
                        
                    case 0xF4:
                        value = int.from_bytes(rom.read(1), 'little')
                        out.write(f'\tRange {value}\n')
                        
                    case 0xF5:
                        value = int.from_bytes(rom.read(1), 'little', signed=True)
                        out.write(f'\tBend {value}\n')
                        
                    case 0xF6:
                        value = int.from_bytes(rom.read(1), 'little')
                        tick += value
                        out.write(f'\tWait {value}\n')
                        
                    case 0xF8:
                        finish = 1
                        value = int.from_bytes(rom.read(2), 'little', signed=True)
                        out.write(f'\tJump\n')
                        jump = linelocation.index(rom.tell() + value)
                        out.seek(lineseek[jump])
                        temp = out.read()
                        out.seek(lineseek[jump])
                        out.write(f'Loop {i}:\n')
                        out.write(temp)
                        
                    case 0xF9:
                        value = int.from_bytes(rom.read(1), 'little')
                        out.write(f'\tBPM {value}\n')
                        
                    case 0xFF:
                        finish = 1
                        out.write(f'\tEnd\n')
                        
                    case _:
                        if byte < 0xF0:
                            if byte == 0:
                                value = int.from_bytes(rom.read(1), 'little') - 0x80
                                if value >= 0:
                                    value2 = int.from_bytes(rom.read(1), 'little')
                                    tick += value2
                                    out.write(f'\tExtend {note_name(value)} {value2}\n')
                                else:
                                    out.write(f'\tExtended {value + 0x80}\n')
                            else:
                                value = int.from_bytes(rom.read(1), 'little')
                                tick += byte
                                out.write(f'\tNote {note_name(value)} {byte}\n')
                        else:
                            out.write(f'\tUNKNOWN {byte}\n')
            
            out.write(f'\n')

def note_name(note):
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return f'{names[note % 12]}{int(note / 12)}'

def note_value(name):
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    numbers = 1
    if len(name) == 3 and name[1] != '#' or len(name) == 4:
        numbers = 2
    
    note = names.index(name[:(len(name) - numbers)])
    
    num = name[len(name) - numbers]
    if numbers == 2:
        num += name[len(name) - 1]
    
    octave = int(num)
    
    return note + (octave * 12)

def get_name(index, list):
    if names and index < len(list) and list[index] != '':
        return list[index]
    else:
        return index

def setup_folder():
    if not os.path.isdir(folder):
        os.makedirs(folder)
    elif os.path.exists(f'{folder}\\-header.txt'):
        os.remove(f'{folder}\\-header.txt')

def inject_samples():
    global free
    
    writtensampleoffset = sampledatastart
    
    with open(f'{folder}\\-header.txt', 'r') as text:
        lines = [line.rstrip() for line in text]
        for file in lines:
            split = file.split()
            
            sample = ''
            if len(split) > 0:
                sample = split[0]
                print(f'Injecting sample {sample}.wav')
                
                if len(split) > 1:
                    loop = int(split[1])
                    hasloop = 1
                else:
                    loop = 0
                    hasloop = 0
                
                with open(f'{folder}\\{sample}.wav', 'rb') as wav:
                    wav.seek(0x10)
                    nextheader = 0x14 + int.from_bytes(wav.read(4), 'little')
                    wav.seek(0x18)
                    samplerate = int.from_bytes(wav.read(4), 'little')
                    wav.seek(nextheader)
                    
                    head = wav.read(4)
                    
                    if not head == b'data': # smpl header probably
                        nextheader += 0x0C + int.from_bytes(wav.read(4), 'little')
                        wav.seek(nextheader)
                    
                    samplecount = int.from_bytes(wav.read(4), 'little')
                    samples = wav.read(samplecount)
                
                end = writtensampleoffset + 0x10 + samplecount
                if end > sampledataend and writtensampleoffset < free:
                    writtensampleoffset = free
                
                outrom.seek(sampletable + (len(samplelist) * 4))
                outrom.write((writtensampleoffset - sampletable).to_bytes(4, 'little'))
                
                outrom.seek(writtensampleoffset)
                outrom.write((hasloop << 30).to_bytes(4, 'little'))
                outrom.write((samplerate << 10).to_bytes(4, 'little'))
                outrom.write((loop).to_bytes(4, 'little'))
                outrom.write(samplecount.to_bytes(4, 'little'))
                outrom.write(samples)
                
                writtensampleoffset += 0x10 + samplecount
                writtensampleoffset += samplecount % 2 # even sizes only (IMPORTANT)
                writtensampleoffset += writtensampleoffset % 4 # align (IMPORTANT)
                if writtensampleoffset > free:
                    free = writtensampleoffset
                
            samplelist.append(sample)

def inject_instruments():
    writteninstrumentoffset = instrumentdatastart
    
    with open(f'{folder}\\-header.txt', 'r') as text:
        lines = [line.rstrip() for line in text]
        for file in lines:
            if len(file) > 0:
                print(f'Injecting instrument {file}.txt')
                
                outrom.seek(instrumenttable + (len(instrumentlist) * 2))
                outrom.write((writteninstrumentoffset - instrumenttable).to_bytes(2, 'little'))
                
                with open(f'{folder}\\{file}.txt', 'r') as inst:
                    segments = [line.rstrip() for line in inst]
                    output = b''
                    for segment in segments:
                        split = segment.split()
                        
                        notelow = int.to_bytes(int(split[0]), 1)
                        notehigh = int.to_bytes(int(split[1]), 1)
                        
                        sample = split[2]
                        if not sample.isdigit():
                            if sample in samplelist:
                                sample = samplelist.index(sample)
                            else:
                                print(f'\033[31mINVALID SAMPLE: {sample}\033[0m')
                                sample = 0xFF
                        sample = int.to_bytes(int(sample), 1)
                        
                        unpitched = int.to_bytes(int(split[3]) << 7, 1)
                        attack = int.to_bytes(int(split[4]), 1)
                        decay = int.to_bytes(int(split[5]), 1)
                        sustain = int.to_bytes(int(split[6]), 1)
                        release = int.to_bytes(int(split[7]), 1)
                        
                        output = notelow + notehigh + sample + unpitched + attack + decay + sustain + release
                        
                        outrom.seek(writteninstrumentoffset)
                        outrom.write(output)
                        writteninstrumentoffset += 0x08
            else:
                outrom.seek(instrumenttable + (len(instrumentlist) * 2))
                outrom.write((writteninstrumentoffset - instrumenttable).to_bytes(2, 'little'))
            instrumentlist.append(file)

def inject_songs():
    global free
    
    writtensongoffset = songdatastart
    
    with open(f'{folder}\\-header.txt', 'r') as text:
        lines = [line.rstrip() for line in text]
        for file in lines:
            if len(file) > 0:
                print(f'Injecting song {file}.txt')
                
                outrom.seek(songtable + (len(songlist) * 4))
                outrom.write((writtensongoffset + 0x08000000).to_bytes(4, 'little'))
                
                global usedtracks
                global enabledtracks
                global tracks
                with open(f'{folder}\\{file}.txt', 'r') as song:
                    decode_song(song)
                    
                size = 2 + (len(enabledtracks) * 2)
                tracklocations = []
                for track in enabledtracks:
                    tracklocations.append(size)
                    size += len(tracks[track])
                
                end = writtensongoffset + size
                if end > songdataend and writtensongoffset < free:
                    writtensongoffset = free
                
                outrom.seek(writtensongoffset)
                outrom.write(usedtracks.to_bytes(2, 'little'))
                for i in range(len(enabledtracks)):
                    outrom.write(tracklocations[i].to_bytes(2, 'little'))
                for track in enabledtracks:
                    outrom.write(tracks[track])
                
                writtensongoffset += size
                writtensongoffset += writtensongoffset % 4 # align
                
            songlist.append(file)

def decode_song(song):
    global usedtracks
    global enabledtracks
    global tracks
    
    lines = [line.rstrip() for line in song]
    tracks = [bytearray() for _ in range(12)]
    usedtracks = 0
    written = 0
    enabledtracks = []
    
    for line in lines:
        split = line.split()
        if len(split) > 0:
            opcode = line.split()[0]
            match opcode:
                case '--------':
                    pass
                    
                case 'Extend': # 00
                    note = note_value(line.split()[1]) + 0x80
                    length = int(line.split()[2])
                    tracks[track] += b'\x00' + note.to_bytes(1) + length.to_bytes(1)
                    written += 3
                    
                case 'Note': # 01-7F
                    note = note_value(line.split()[1])
                    length = int(line.split()[2])
                    tracks[track] += length.to_bytes(1) + note.to_bytes(1)
                    written += 2
                    
                case 'Loop':
                    loop = written
                    
                case 'Track':
                    track = int(line.split()[1].split(':')[0])
                    usedtracks += 1 << track
                    enabledtracks.append(track)
                    
                case 'Instrument': # 0xF0
                    value = line.split()[1]
                    
                    if not value.isdigit():
                        if value in instrumentlist:
                            value = instrumentlist.index(value)
                        else:
                            value = 0xFF
                    value = int(value)
                    
                    tracks[track] += b'\xF0' + value.to_bytes(1)
                    written += 2
                    
                case 'Volume': # 0xF1
                    value = int(line.split()[1])
                    tracks[track] += b'\xF1' + value.to_bytes(1)
                    written += 2
                    
                case 'Pan': # 0xF2
                    value = 0x80 - int(line.split()[1])
                    tracks[track] += b'\xF2' + value.to_bytes(1)
                    written += 2
                    
                case 'Range': # 0xF4
                    value = int(line.split()[1])
                    tracks[track] += b'\xF4' + value.to_bytes(1)
                    written += 2
                    
                case 'Bend': #0xF5
                    value = int(line.split()[1])
                    tracks[track] += b'\xF5' + value.to_bytes(1, signed=True)
                    written += 2
                    
                case 'Wait': # 0xF6
                    value = int(line.split()[1])
                    tracks[track] += b'\xF6' + value.to_bytes(1)
                    written += 2
                    
                case 'Jump': # 0xF8
                    value = loop - written - 3
                    tracks[track] += b'\xF8' + value.to_bytes(2, 'little', signed=True)
                    
                case 'BPM': # 0xF9
                    value = int(line.split()[1])
                    tracks[track] += b'\xF9' + value.to_bytes(1)
                    written += 2
                    
                case 'End': # 0xFF
                    tracks[track] += b'\xFF'
                    written += 1

if len(sys.argv) < 2:
    print("you forgot the rom")
    sys.exit()

global pack
pack = input('Unpack/Repack? (Default 0) [0/1]: ')
if pack == '': pack = 0
pack = int(pack)

if not pack:
    global names
    names = input('Use names? (Default 1) [0/1]: ')
    if names == '': names = 1
    names = int(names)

global songtable
global songcount
global songnames
global instrumenttable
global instrumentcount
global instrumentnames
global sampletable
global samplecount
global samplenames

with open('names_songs.txt', 'r') as text:
    songnames = [line.rstrip() for line in text]
with open('names_instruments.txt', 'r') as text:
    instrumentnames = [line.rstrip() for line in text]
with open('names_samples.txt', 'r') as text:
    samplenames = [line.rstrip() for line in text]

global header

with open(sys.argv[1], 'rb') as rom:
    rom.seek(0xAC)
    id = rom.read(4)
    
    global free
    match id:
        case b'A88E':
            songtable           = 0x21CB70
            songcount           = 407
            songdatastart       = 0x19BB2C
            songdataend         = 0x1DA690
            instrumenttable     = 0x21D1CC
            instrumentcount     = 260
            instrumentdatastart = 0x21D3D6
            instrumentdataend   = 0x21DB56
            sampletable         = 0xA806B8
            samplecount         = 236
            sampledatastart     = 0xA80A68
            sampledataend       = 0xCDB62C
            free                = 0xCDD2F0
        case b'A88J':
            songtable           = 0x205060
            songcount           = 418
            songdatastart       = 0x193320
            songdataend         = 0x1D209C
            instrumenttable     = 0x2056E8
            instrumentcount     = 260
            instrumentdatastart = 0x2058F2
            instrumentdataend   = 0x206092
            sampletable         = 0x9721A8
            samplecount         = 239
            sampledatastart     = 0x972564
            sampledataend       = 0xBDA8E4
            free                = 0xBDC5A0
        case b'\x00\x00\x00\x00':
            songtable           = 0x116BA0
            songcount           = 172
            instrumenttable     = 0x116E54
            instrumentcount     = 260
            sampletable         = 0x5C6730
            samplecount         = 150
            free                = 0x6BB570
            id                  = b'E303'
    
    if not pack:
        # extract samples
        folder = f'{id.decode()}_samples'
        setup_folder()
        header = ''
        for sampleindex in range(samplecount):
            rom.seek(sampletable + (sampleindex * 4))
            offset = int.from_bytes(rom.read(4), 'little') + sampletable
            
            if offset > sampletable:
                extract_sample(offset)
            else:
                header += '\n'
        with open(f'{folder}\\-header.txt', 'a') as out: out.write(header)
        
        # extract instruments
        folder = f'{id.decode()}_instruments'
        setup_folder()
        header = ''
        for instrumentindex in range(instrumentcount):
            rom.seek(instrumenttable + (instrumentindex * 2))
            offset = int.from_bytes(rom.read(2), 'little') + instrumenttable
            sections = ((int.from_bytes(rom.read(2), 'little') + instrumenttable) - offset) >> 3
            
            if offset > instrumenttable and sections > 0:
                extract_instrument(offset, sections)
            else:
                header += '\n'
        with open(f'{folder}\\-header.txt', 'a') as out: out.write(header)
        
        # extract songs
        # TODO: final 54 = demo 13
        folder = f'{id.decode()}_songs'
        setup_folder()
        header = ''
        for songindex in range(songcount):
            rom.seek(songtable + (songindex * 4))
            offset = int.from_bytes(rom.read(4), 'little') - 0x08000000
            
            if offset > 0:
                extract_song(offset)
            else:
                header += '\n'
        with open(f'{folder}\\-header.txt', 'a') as out: out.write(header)
        
    else:
        id = input('ID? (Default mod): ')
        if id == '':
            id = 'mod'
        
        with open('temp.gba', 'w+b') as outrom:
            rom.seek(0)
            outrom.write(rom.read())
            
            # clear samples
            outrom.seek(sampletable)
            outrom.write(b'\x00' * samplecount * 4)
            outrom.seek(sampledatastart)
            outrom.write(b'\x00' * (sampledataend - sampledatastart))
            # inject samples
            folder = f'{id}_samples'
            samplelist = []
            inject_samples()
            
            # clear instruments
            outrom.seek(instrumenttable)
            outrom.write(b'\x00' * instrumentcount * 2)
            outrom.seek(instrumentdatastart)
            outrom.write(b'\x00' * (instrumentdataend - instrumentdatastart))
            # inject instruments
            folder = f'{id}_instruments'
            instrumentlist = []
            inject_instruments()
            
            # clear songs
            outrom.seek(songtable)
            outrom.write(b'\x00' * songcount * 4)
            outrom.seek(songdatastart)
            outrom.write(b'\x00' * (songdataend - songdatastart))
            # inject songs
            folder = f'{id}_songs'
            songlist = []
            inject_songs()