import sys
import os
import numpy as np
import math

def load_wave(id):
    global wavehasloop
    global waverate
    global waveloop
    global wavelength
    global wave
    global instrument
    global pan
    
    temp = rom.tell()
    
    if not pulse:
        rom.seek(wavetable + (id * 4))
        offset = int.from_bytes(rom.read(4), 'little') + wavetable
        rom.seek(offset)
        
        wavehasloop = int.from_bytes(rom.read(4), 'little') >> 30
        waverate = int.from_bytes(rom.read(4), 'little') >> 10
        waveloop = int.from_bytes(rom.read(4), 'little')
        wavelength = int.from_bytes(rom.read(4), 'little')
        wave = rom.read(wavelength)
    else:
        wavehasloop = 1
        waveloop = 0
        wavelength = 8
        waverate = (440 * (2 ** (-9 / 12))) * wavelength
        h = 0.75 * 255
        l = 0.25 * 255
        
        waves = [[h,l,l,l,l,l,l,l],[h,h,l,l,l,l,l,l],[h,h,h,h,l,l,l,l],[h,h,h,h,h,h,l,l]]
        wave = waves[id % 4]
        
        pan *= 255
        pan = min(max(pan, -1), 1)
    
    rom.seek(temp)

def read_song():
    global offset
    rom.seek(offset)
    
    global bpm
    global wait
    global volume
    global extend
    global wavesample
    global playing
    global instrument
    global pan
    global finish
    global note
    global bendrange
    global bend
    global adsr
    global adsrtype
    
    byte = int.from_bytes(rom.read(1), 'little')
    
    match byte:
        case 0xF0:
            instrument = int.from_bytes(rom.read(1), 'little')
            
        case 0xF1:
            prevvolume = volume
            volume = int.from_bytes(rom.read(1), 'little') / 255
            if playing and not extend:
                adsrtype = 3
                adsr *= prevvolume / volume
            
        case 0xF2:
            value = 0x80 - int.from_bytes(rom.read(1), 'little')
            if value < 1:
                pan = value / 127
            else:
                pan = (value - 1) / 127
            
        case 0xF4:
            bendrange = int.from_bytes(rom.read(1), 'little')
            
        case 0xF5:
            bend = int.from_bytes(rom.read(1), 'little', signed=True)
            sample_pitch(note)
            
        case 0xF6:
            wait += int.from_bytes(rom.read(1), 'little')
            if playing and not extend:
                adsrtype = 3
            
        case 0xF8:
            jump = int.from_bytes(rom.read(2), 'little', signed=True)
            finish += 0.5
            offset += jump
            rom.seek(offset + 3)
            if playing and not extend:
                adsrtype = 3
            
        case 0xF9:
            bpm = int.from_bytes(rom.read(1), 'little')
            
        case 0xFF:
            finish = 255
            wait += 48
            if playing:
                adsrtype = 3
            
        case _:
            if byte < 0xF0:
                if byte == 0:
                    note = int.from_bytes(rom.read(1), 'little') - 0x80
                    if note >= 0:
                        value2 = int.from_bytes(rom.read(1), 'little')
                        wait += value2
                        if not extend:
                            if not pulse:
                                wavesample = 0
                            playing = 1
                            adsr = 0
                            adsrtype = 0
                        extend = 1
                        play_note(note)
                else:
                    note = int.from_bytes(rom.read(1), 'little')
                    wait += byte
                    if not extend:
                        if not pulse:
                            wavesample = 0
                        playing = 1
                        adsr = 0
                        adsrtype = 0
                    extend = 0
                    play_note(note)
    offset = rom.tell()

def get_sample(wave, sample, volume):
    return (wave[sample] - 0x80) * volume

def sample_pitch(note):
    global samplerate
    global waverate
    global bend
    global bendrange
    
    pitch = note + ((bend / 128) * bendrange)
    
    samplerate = waverate * (2 ** ((pitch - 60)/12))

def play_note(note):
    global instrument
    
    global playing
    global adsr
    global adsrtype
    
    global attack
    global decay
    global sustain
    global release
    
    temp = rom.tell()
    
    att = 0
    instmin = -1
    instmax = -1
    
    rom.seek(instrumenttable + ((instrument + 1) * 2))
    end = int.from_bytes(rom.read(2), 'little') + instrumenttable
    while not instmin <= note <= instmax:
        rom.seek(instrumenttable + (instrument * 2))
        offset = int.from_bytes(rom.read(2), 'little') + instrumenttable
        rom.seek(offset + (att * 8))
        
        instmin = int.from_bytes(rom.read(1), 'little')
        instmax = int.from_bytes(rom.read(1), 'little')
        att += 1
    
    if rom.tell() > end:
        playing = 0
        adsr = 0
        adsrtype = 4
        return
    
    load_wave(int.from_bytes(rom.read(1), 'little'))
    unpitched = int.from_bytes(rom.read(1), 'little')
    
    attack = int.from_bytes(rom.read(1), 'little')
    decay = int.from_bytes(rom.read(1), 'little')
    sustain = int.from_bytes(rom.read(1), 'little')
    release = int.from_bytes(rom.read(1), 'little')
    
    rom.seek(temp)
    
    if unpitched:
        sample_pitch(60)
    else:
        sample_pitch(note)

def tick():
    global nexttick
    global bpm
    global currenttick
    nexttick += int((1.25 / bpm) * outrate * (60 / (262144.0 / 4389.0)))
    currenttick += 1
    if currenttick % 192 == 0:
        print(currenttick)

def calculate_adsr():
    global playing
    global adsr
    global adsrtype
    
    if adsrtype == 0:
        if attack == 255:
            adsr = 1
            adsrtype += 1
        else:
            adsr += adsr_formula(attack)
            if adsr >= 1:
                adsrtype += 1
                return
    if adsrtype == 1 and decay < 255: # sustain ONLY works if decay is active
        adsr -= adsr_formula(decay)
        if adsr <= sustain / 255:
            adsrtype += 1
            return
    if adsrtype == 2:
        adsr == sustain / 255
    if adsrtype == 3:
        if release == 255:
            playing = 0
            adsr = 0
            adsrtype = 4
        else:
            adsr -= adsr_formula(release)
            if adsr <= 0:
                playing = 0
                adsr = 0
                adsrtype = 4
                return

def adsr_formula(value):
    # volume only factors into psg, not pcm
    if pulse:
        return 255 / (outrate * 1.3 * volume * (255 - value))
    else:
        return value / (255 * outrate * 0.015)

def should_render():
    return finish < 1 or maxxed < 1 or (finish == 255 and adsrtype != 4)

def render(track):
    global samplerate
    global nexttick
    global currenttick
    global currentsample
    global bpm
    global wait
    global volume
    global extend
    global wavesample
    global instrument
    global pan
    global finish
    global offset
    global bendrange
    global bend
    global note
    global pulse
    global maxxed
    
    global wavehasloop
    global waverate
    global waveloop
    global wavelength
    global wave
    
    global attack
    global decay
    global sustain
    global release
    
    global playing
    global adsr
    global adsrtype
    
    global endsample
    
    rom.seek(offset + (track * 2))
    offset += int.from_bytes(rom.read(2), 'little')
    rom.seek(offset)
    
    nexttick = 0
    currenttick = 0
    
    out = []
    bend = 0
    bendrange = 0
    wavesample = 0
    wait = 0
    volume = 255
    currentsample = 0
    extend = 0
    pan = 0
    finish = 0
    instrument = 0
    
    playing = 0
    adsr = 0
    adsrtype = 4
    
    pulse = channel > 7
    
    mastervolume = 0.5
    maxxed = 0
    
    while should_render():
        while wait <= currenttick and finish < 255:
            read_song()
        tick()
        
        if not playing and adsrtype != 4:
            print(f'{playing} {adsrtype}')
        
        for _ in range(math.ceil(nexttick - currentsample)):
            if not should_render():
                break
            
            if playing:
                calculate_adsr()
                
                if adsrtype != 4:
                    sampleL = get_sample(wave, int(wavesample), volume * adsr * playing * (1 - max(pan, 0)) * mastervolume)
                    sampleR = get_sample(wave, int(wavesample), volume * adsr * playing * (min(pan, 0) + 1) * mastervolume)
                    out.extend([int(sampleL * 256), int(sampleR * 256)])
                    
                    wavesample += (samplerate / outrate)
                    if wavesample >= len(wave):
                        if not wavehasloop:
                            playing = 0
                            adsr = 0
                            adsrtype = 4
                        wavesample = waveloop + (wavesample % 1)
                else:
                    out.extend([0, 0])
            else:
                out.extend([0, 0])
            
            # not accurate but keeps loops consistent
            if pulse and adsr == 0:
                wavesample = 0
            
            currentsample += 1
            
            if currentsample >= endsample:
                maxxed = 1
                endsample = currentsample
        
    return out

with open(f'{input()}.gba', 'rb') as rom:
    songtable = 0x21CB70
    instrumenttable = 0x21D1CC
    wavetable = 0xA806B8
    
    #songtable = 0x116BA0
    #instrumenttable = 0x116E54
    #wavetable = 0x5C6730
    
    #outrate = 15768
    outrate = 48000
    
    songindex = int(input())
    
    for i in range(int(input())):
        global endsample
        endsample = 0
        prevmax = 0
        
        rom.seek(songtable + (songindex * 4))
        song = int.from_bytes(rom.read(4), 'little') - 0x08000000
        
        rom.seek(song)
        
        trackbits = int.from_bytes(rom.read(2), 'little')
        
        tracksenabled = []
        for i in range(12):
            if trackbits >> i & 1:
                tracksenabled.append(i)
        
        trackoffset = [0] * 12
        for i in tracksenabled:
            trackoffset[i] = int.from_bytes(rom.read(2), 'little')
        
        retry = 1
        while retry:
            track = 0
            retry = 0
            
            for channel in tracksenabled:
                if retry == 0:
                    track += 1
                    
                    global offset
                    offset = song
                    
                    rendered = render(track)
                    
                    if endsample > prevmax:
                        prevmax = endsample
                        if track > 1: retry = 1
                    
                    print(f'ENDSAMPLE: {endsample}')
                    
                    with open(f'{songindex}_{channel}.wav', 'wb') as out:
                        out.write('RIFF'.encode('ascii'))
                        out.write((len(rendered) * 2 + 36).to_bytes(4, 'little')) # riff size
                        out.write('WAVEfmt '.encode('ascii'))
                        out.write((16).to_bytes(4, 'little')) # fmt size
                        out.write((1).to_bytes(2, 'little')) # type
                        out.write((2).to_bytes(2, 'little')) # channels
                        out.write((outrate).to_bytes(4, 'little')) # sample rate
                        out.write((outrate * 2 * 2).to_bytes(4, 'little')) # sample rate * bytes * channels
                        out.write((2 * 2).to_bytes(2, 'little')) # bytes * channels
                        out.write((16).to_bytes(2, 'little')) # bits
                        
                        out.write('data'.encode('ascii'))
                        out.write((len(rendered) * 2).to_bytes(4, 'little')) # data size
                        out.write(np.array(rendered, np.int16))
                    
            if retry == 0:
                songindex += 1