import sys
import os
import numpy as np
import math

expectedFramerate = 60
gbaFramerate = (262144.0 / 4389.0)
#samplesPerFrame = 264 # 15768.060150375939 hz
samplesPerFrame = 800 # 47782.00045568466 hz

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
    global adsrtype
    
    global ERAM_Flags
    global ERAM_BPM
    global ERAM_UnkCounter
    global ERAM_ChannelStart
    global ERAM_ChannelOffset
    global ERAM_Wait
    global ERAM_Note
    global ERAM_Instrument
    global ERAM_Volume
    global ERAM_Pan
    global ERAM_PitchRange
    global ERAM_PitchAmount
    global ERAM_Unk11
    global ERAM_Channel
    global ERAM_Unk13
    global ERAM_Unk14
    global ERAM_Unk15
    global ERAM_Unk16
    global ERAM_Unk17
    global ERAM_Unk18
    global ERAM_Unk19
    global ERAM_Unk1A
    global ERAM_Unk1B
    global ERAM_Unk1C
    global ERAM_Unk1D
    global ERAM_Unk1E
    global ERAM_Unk1F
    
    # TODO: IRAM should not be involved
    global IRAM_ADSR
    global IRAM_Flags
    
    byte = int.from_bytes(rom.read(1), 'little')
    
    match byte:
        case 0xF0:
            ERAM_Instrument = int.from_bytes(rom.read(1), 'little')
            
            instrument = ERAM_Instrument
            
        case 0xF1:
            ERAM_Volume = int.from_bytes(rom.read(1), 'little')
            
            prevvolume = volume
            volume = ERAM_Volume / 255
            if playing and not extend:
                IRAM_Flags |= 0x40 # TODO: not actually what it does
                adsrtype = 3
            
        case 0xF2:
            ERAM_Pan = int.from_bytes(rom.read(1), 'little')
            
            value = 0x80 - ERAM_Pan
            if value < 1:
                pan = value / 127
            else:
                pan = (value - 1) / 127
            
        case 0xF4:
            ERAM_PitchRange = int.from_bytes(rom.read(1), 'little')
            
            bendrange = ERAM_PitchRange
            
        case 0xF5:
            ERAM_PitchAmount = int.from_bytes(rom.read(1), 'little', signed=True)
            
            bend = ERAM_PitchAmount
            sample_pitch(note)
            
        case 0xF6:
            ERAM_Wait = int.from_bytes(rom.read(1), 'little')
            
            wait += ERAM_Wait
            if playing and not extend:
                IRAM_Flags |= 0x40 # TODO: not actually what it does
                adsrtype = 3
            
        case 0xF8:
            #ERAM_ChannelOffset += 2 + int.from_bytes(rom.read(2), 'little', signed=True)
            
            jump = int.from_bytes(rom.read(2), 'little', signed=True)
            finish += 0.5
            offset += jump
            rom.seek(offset + 3)
            if playing and not extend:
                IRAM_Flags |= 0x40 # TODO: not actually what it does
                adsrtype = 3
            
        case 0xF9:
            ERAM_BPM = int.from_bytes(rom.read(1), 'little')
            
        case 0xFF:
            if ERAM_Flags & 0x0080 != 0:
                pass # TODO: figure out 0x0819b852
            ERAM_Flags = 0x0000
            
            finish = 255
            wait += 48
            if playing:
                IRAM_Flags |= 0x40 # TODO: not actually what it does
                adsrtype = 3
            
        case _:
            if byte < 0xE0:
                note = int.from_bytes(rom.read(1), 'little')
                ERAM_Note = note % 0x7F
                
                if ERAM_Flags & 0x0040 == 0:
                    if ERAM_Flags & 0x0800 != 0:
                        ERAM_Flags &= 0xCFFF
                        ERAM_Unk17 = ERAM_Unk16
                    if ERAM_Flags & 0x0100 != 0:
                        ERAM_Flags &= 0xF9FF
                        ERAM_Unk1B = ERAM_Unk1A
                    # TODO: figure out 0x0819b5fa
                    # TODO: figure out 0x0819b602
                    ERAM_Flags |= 0x0080
                else:
                    # TODO: figure out 0x0819b5c2
                    ERAM_Flags &= 0xFFBF
                
                if byte != 0:
                    if note & 0x80 != 0:
                        ERAM_Flags |= 0x0020
                    ERAM_Wait = byte
                else:
                    ERAM_Flags |= 0x0040
                    if note & 0x80 != 0:
                        ERAM_Wait = int.from_bytes(rom.read(1), 'little')
                
                # TODO: remove this after flags and IRAM are working
                if not extend:
                    if not pulse:
                        wavesample = 0
                    playing_start()
                
                extend = note & 0x80
                play_note(note & 0x7F)
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
    global adsrtype
    
    global IRAM_Attack
    global IRAM_Decay
    global IRAM_Sustain
    global IRAM_Release
    
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
        playing_stop()
    
    load_wave(int.from_bytes(rom.read(1), 'little'))
    unpitched = int.from_bytes(rom.read(1), 'little')
    
    IRAM_Attack = int.from_bytes(rom.read(1), 'little')
    IRAM_Decay = int.from_bytes(rom.read(1), 'little')
    IRAM_Sustain = int.from_bytes(rom.read(1), 'little')
    IRAM_Release = int.from_bytes(rom.read(1), 'little')
    
    rom.seek(temp)
    
    if unpitched:
        sample_pitch(60)
    else:
        sample_pitch(note)

# TODO: make frame based instead of tick based
def tick():
    global nexttick
    global currenttick
    
    nexttick += int((1.25 / ERAM_BPM) * outrate * (expectedFramerate / gbaFramerate))
    currenttick += 1
    if currenttick % 192 == 0:
        print(currenttick)

# based on 0x0819a2f0
def calculate_adsr():
    global playing
    global adsrtype
    global adsrFrameCounter
    
    global IRAM_Flags
    global IRAM_ADSR
    
    if not pulse: # TODO: check code, MAYBE pulse doesnt get tied to framerate?
        if adsrFrameCounter > 0:
            adsrFrameCounter -= gbaFramerate / outrate
            return
        
        adsrFrameCounter += 1
        
        if IRAM_Flags != 0x00:
            if IRAM_Flags == 0x80:
                IRAM_ADSR = IRAM_Attack
                IRAM_Flags += 1
            else:
                adsrBackup = IRAM_ADSR
                if IRAM_Flags == 0x81:
                    IRAM_ADSR += IRAM_Attack
                    if IRAM_ADSR >= 255:
                        IRAM_ADSR = 255
                        IRAM_Flags += 1
                    return
                if IRAM_Flags == 0x82:
                    IRAM_ADSR -= IRAM_Decay
                    if adsrBackup >= IRAM_Decay or IRAM_Sustain > 128:
                        IRAM_ADSR = IRAM_Sustain
                    return
                if IRAM_Flags != 0x83:
                    IRAM_ADSR -= IRAM_Release
                    if adsrBackup < IRAM_Release or IRAM_ADSR == 0:
                        IRAM_Flags = 0
                    return
    else: # TODO: find pulse adsr code
        if adsrtype == 0:
            if IRAM_Attack == 255:
                IRAM_ADSR = 255
                adsrtype += 1
            else:
                IRAM_ADSR += adsr_formula(IRAM_Attack)
                if IRAM_ADSR >= 255:
                    IRAM_ADSR = 255
                    adsrtype += 1
                    return
        if adsrtype == 1 and IRAM_Decay < 255: # sustain ONLY works if decay is active
            IRAM_ADSR -= adsr_formula(IRAM_Decay)
            if IRAM_ADSR <= IRAM_Sustain:
                IRAM_ADSR = IRAM_Sustain
                return
        if adsrtype == 2:
            IRAM_ADSR == IRAM_Sustain
        if adsrtype == 3:
            if IRAM_Release == 255:
                playing_stop()
                return
            else:
                IRAM_ADSR -= adsr_formula(IRAM_Release)
                if IRAM_ADSR <= 0:
                    playing_stop()
                    return

def adsr_formula(value):
    return (255 / (outrate * volume * (255 - value))) * 255

def playing_start(): # TODO: figure out how this works and what it sets
    global playing
    global adsrtype
    global adsrFrameCounter
    
    global IRAM_Flags
    global IRAM_ADSR
    
    IRAM_Flags = 0x80
    playing = 1
    IRAM_ADSR = 0
    adsrtype = 0
    adsrFrameCounter = 0

def playing_stop(): # TODO: figure out how this works and what it sets
    global playing
    global adsrtype
    
    global IRAM_Flags
    global IRAM_ADSR
    
    IRAM_Flags = 0x00
    playing = 0
    IRAM_ADSR = 0
    adsrtype = 4

def should_render():
    return (finish < 1 or maxxed < 1 or (finish == 255 and adsrtype != 4)) and currenttick < 20000 # TODO: remove cap after iram and stuff are working

def render(track):
    global samplerate
    global nexttick
    global currenttick
    global currentsample
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
    global adsrtype
    
    global endsample
    
    global ERAM_Flags
    global ERAM_BPM
    global ERAM_UnkCounter
    global ERAM_ChannelStart
    global ERAM_ChannelOffset
    global ERAM_Wait
    global ERAM_Note
    global ERAM_Instrument
    global ERAM_Volume
    global ERAM_Pan
    global ERAM_PitchRange
    global ERAM_PitchAmount
    global ERAM_Unk11
    global ERAM_Channel
    global ERAM_Unk13
    global ERAM_Unk14
    global ERAM_Unk15
    global ERAM_Unk16
    global ERAM_Unk17
    global ERAM_Unk18
    global ERAM_Unk19
    global ERAM_Unk1A
    global ERAM_Unk1B
    global ERAM_Unk1C
    global ERAM_Unk1D
    global ERAM_Unk1E
    global ERAM_Unk1F
    
    global IRAM_Flags
    global IRAM_ADSR
    global IRAM_Sample
    global IRAM_Unpitched
    global IRAM_SamplePlayback
    global IRAM_VolumeRight
    global IRAM_VolumeLeft
    global IRAM_Pitch
    global IRAM_Note
    global IRAM_Attack
    global IRAM_Decay
    global IRAM_Sustain
    global IRAM_Release
    
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
    volume = 200
    currentsample = 0
    extend = 0
    pan = 0
    finish = 0
    instrument = 0
    
    playing_stop()
    
    pulse = channel > 7
    
    mastervolume = 0.5
    maxxed = 0
    
    # DEFAULTS from 0x0819b040
    ERAM_Flags = 0x0083
    ERAM_ChannelStart = 0 # TODO: figure this out
    ERAM_ChannelOffset = 0
    ERAM_BPM = 120
    ERAM_UnkCounter = 0
    ERAM_Instrument = 0
    ERAM_Pan = 127
    ERAM_Wait = 1
    ERAM_Volume = 200
    ERAM_PitchAmount = 0
    ERAM_PitchRange = 2
    ERAM_Unk11 = 0
    
    # TOOD: find out what these init to
    IRAM_Flags = 0
    IRAM_ADSR = 0
    IRAM_Sample = 0
    IRAM_Unpitched = 0
    IRAM_SamplePlayback = 0
    IRAM_VolumeRight = 0
    IRAM_VolumeLeft = 0
    IRAM_Pitch = 0
    IRAM_Note = 0
    IRAM_Attack = 0
    IRAM_Decay = 0
    IRAM_Sustain = 0
    IRAM_Release = 0
    
    while should_render():
        while ERAM_Wait <= 0 and finish < 255:
            read_song()
        tick()
        ERAM_Wait -= 1
        
        for _ in range(math.ceil(nexttick - currentsample)):
            if not should_render():
                break
            
            if playing and IRAM_Flags & 0x80:
                calculate_adsr()
                
                if adsrtype != 4 and IRAM_Flags & 0x80:
                    sampleL = get_sample(wave, int(wavesample), volume * (IRAM_ADSR / 255) * (1 - max(pan, 0)) * mastervolume)
                    sampleR = get_sample(wave, int(wavesample), volume * (IRAM_ADSR / 255) * (min(pan, 0) + 1) * mastervolume)
                    out.extend([int(sampleL * 256), int(sampleR * 256)])
                    
                    wavesample += (samplerate / outrate)
                    if wavesample >= len(wave):
                        if not wavehasloop:
                            playing_stop()
                        wavesample = waveloop + (wavesample % 1)
                else:
                    out.extend([0, 0])
            else:
                out.extend([0, 0])
            
            # not accurate but keeps loops consistent
            if pulse and IRAM_ADSR == 0:
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