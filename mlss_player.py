import sys
import os
import numpy as np
import math

expectedFramerate = 60
gbaFramerate = (262144.0 / 4389.0)
samplesPerFrame = 264 # 15768.060150375939 hz
#samplesPerFrame = 800 # 47782.00045568466 hz
upsample = 3

outrate = round(samplesPerFrame * gbaFramerate)

global loopCount


PLAYBACK_ACTIVE = 1 << 0
PLAYBACK_INIT = 1 << 1
PLAYBACK_UNK0004 = 1 << 2
PLAYBACK_UNK0008 = 1 << 3
PLAYBACK_UNK0010 = 1 << 4
PLAYBACK_UNK0020 = 1 << 5
PLAYBACK_EXTEND = 1 << 6
PLAYBACK_PLAYING = 1 << 7
PLAYBACK_UNK0100 = 1 << 8
PLAYBACK_UNK0200 = 1 << 9
PLAYBACK_UNK0400 = 1 << 10
PLAYBACK_UNK0800 = 1 << 11
PLAYBACK_UNK1000 = 1 << 12
PLAYBACK_UNK2000 = 1 << 13
PLAYBACK_UNK4000 = 1 << 14
PLAYBACK_UNK8000 = 1 << 15


def set_instrument():
    if pulse:
        set_instrument_pcm() # TODO: set_instrument_psg
    else:
        set_instrument_pcm()

def set_volume():
    if pulse:
        set_pan_psg() # TODO: set_volume_psg
    else:
        set_panvolume_pcm()

def set_pan():
    if pulse:
        set_pan_psg()
    else:
        set_panvolume_pcm()

def set_pitch():
    if pulse:
        set_pitch_pcm() # TODO: set_pitch_psg
    else:
        set_pitch_pcm()

# sub_819A834
def set_panvolume_pcm():
    global PCM_VolumeRight
    global PCM_VolumeLeft
    
    if Track_Pan >= 0x80:
        right = 0xFF - Track_Pan
        left = 0x7F
    else:
        right = 0x7F
        left = Track_Pan
    
    volume = Track_Volume
    
    if Track_Flags & 0x0800 != 0:
        if Track_Flags & 0x1000 == 0:
            unk = 0
        elif Track_Flags & 0x2000 == 0:
            unk = Track_Unk14
        else:
            unk = -Track_Unk14
        
        volume -= unk
        min(max(volume, 0), 255)
    
    # TODO: 0819a87a Unk13
    PCM_VolumeRight = volume * right >> 8
    PCM_VolumeLeft = volume * left >> 8

# based on 0x0819a79c
def set_pitch_pcm():
    global PCM_Pitch
    global PCM_Note
    
    pitch = Track_Note * 0x100 + Track_PitchAmount * Track_PitchRange * 2 + Track_Unk11
    
    if Track_Flags & 0x0100 != 0:
        if Track_Flags & 0x0200 == 0:
            unk = 0
        elif Track_Flags & 0x0400 == 0:
            unk = Track_Unk18
        else:
            unk = -Track_Unk18
        
        pitch += unk
    
    PCM_Pitch = pitch & 0xFF
    PCM_Note = pitch >> 8

# sub_819A7EC
def set_instrument_pcm():
    temp = rom.tell() # TODO: use eram channel start and offset variables so it doesnt have to be backed and restored
    
    global PCM_Flags
    global PCM_Sample
    global PCM_Unpitched
    global PCM_Attack
    global PCM_Decay
    global PCM_Sustain
    global PCM_Release
    global PCM_SamplePlayback
    
    PCM_Flags = 0x00
    region = get_instrument_region(Track_Instrument, Track_Note)
    
    if region != 0:
        set_pitch()
        
        PCM_Sample = int.from_bytes(rom.read(1), 'little')
        PCM_Unpitched = int.from_bytes(rom.read(1), 'little') # TODO: unpitched doesnt exist
        PCM_Attack = int.from_bytes(rom.read(1), 'little')
        PCM_Decay = int.from_bytes(rom.read(1), 'little')
        PCM_Sustain = int.from_bytes(rom.read(1), 'little')
        PCM_Release = int.from_bytes(rom.read(1), 'little')
        PCM_SamplePlayback = 0
        PCM_Flags = 0x80
    
    rom.seek(temp)

# sub_819A8EC
def get_instrument_region(instrument, note):
    rom.seek(instrumenttable + instrument * 2)
    region = instrumenttable + int.from_bytes(rom.read(2), 'little')
    regionEnd = instrumenttable + int.from_bytes(rom.read(2), 'little')
    
    while region != regionEnd:
        rom.seek(region)
        minNote = int.from_bytes(rom.read(1), 'little')
        maxNote = int.from_bytes(rom.read(1), 'little')
        
        if (minNote > note):
            region += 8
            continue
        
        if (maxNote < note):
            region += 8
            continue
        
        return region
    
    return 0

# sub_819AB78
def set_pan_psg():
    global PCM_VolumeRight
    global PCM_VolumeLeft
    
    PCM_VolumeRight = Track_Volume * (Track_Pan <= 128) / 2
    PCM_VolumeLeft = Track_Volume * (Track_Pan >= 127) / 2

# sub_0819B040
def init_eram():
    global Track_Flags, Track_ChannelStart, Track_ChannelOffset, Track_BPM, Track_Unk03, Track_Instrument, Track_Pan, Track_Wait, Track_Volume, Track_PitchAmount, Track_PitchRange, Track_Unk11
    
    Track_Flags = PLAYBACK_PLAYING | PLAYBACK_INIT | PLAYBACK_ACTIVE
    Track_ChannelStart = 0 # TODO: figure this out
    Track_ChannelOffset = 0
    Track_BPM = 120
    Track_Unk03 = 0
    Track_Instrument = 0
    Track_Pan = 127
    Track_Wait = 1
    Track_Volume = 200
    Track_PitchAmount = 0
    Track_PitchRange = 2
    Track_Unk11 = 0

# based on 0x0819b450
def read_song():
    global offset
    rom.seek(offset)
    
    global wavesample
    global playing
    global finish
    global adsrtype
    
    global Track_Flags
    global Track_BPM
    global Track_Unk03
    global Track_ChannelStart
    global Track_ChannelOffset
    global Track_Wait
    global Track_Note
    global Track_Instrument
    global Track_Volume
    global Track_Pan
    global Track_PitchRange
    global Track_PitchAmount
    global Track_Unk11
    global Track_Channel
    global Track_Unk13
    global Track_Unk14
    global Track_Unk15
    global Track_Unk16
    global Track_Unk17
    global Track_Unk18
    global Track_Unk19
    global Track_Unk1A
    global Track_Unk1B
    global Track_Unk1C
    global Track_Unk1D
    global Track_Unk1E
    global Track_Unk1F
    
    # TODO: IRAM should not be involved
    global PCM_Flags
    
    byte = int.from_bytes(rom.read(1), 'little')
    
    match byte:
        case 0xF0:
            Track_Instrument = int.from_bytes(rom.read(1), 'little')
            
        case 0xF1:
            Track_Volume = int.from_bytes(rom.read(1), 'little')
            
            if playing and not Track_Flags & PLAYBACK_EXTEND:
                PCM_Flags |= 0x40 # TODO: not actually what it does
                adsrtype = 3
            
        case 0xF2:
            Track_Pan = int.from_bytes(rom.read(1), 'little')
            
        case 0xF4:
            Track_PitchRange = int.from_bytes(rom.read(1), 'little')
            
        case 0xF5:
            Track_PitchAmount = int.from_bytes(rom.read(1), 'little', signed=True)
            
        case 0xF6:
            Track_Wait = int.from_bytes(rom.read(1), 'little')
            
            if playing and not Track_Flags & PLAYBACK_EXTEND:
                PCM_Flags |= 0x40 # TODO: not actually what it does
                adsrtype = 3
            
        case 0xF8:
            #Track_ChannelOffset += 2 + int.from_bytes(rom.read(2), 'little', signed=True)
            
            if finish == 0: print(f'LOOP {currentsample}')
            
            jump = int.from_bytes(rom.read(2), 'little', signed=True)
            finish += 1
            offset += jump
            rom.seek(offset + 3)
            if playing and not Track_Flags & PLAYBACK_EXTEND:
                PCM_Flags |= 0x40 # TODO: not actually what it does
                adsrtype = 3
            
        case 0xF9:
            Track_BPM = int.from_bytes(rom.read(1), 'little')
            
        case 0xFF:
            if Track_Flags & PLAYBACK_PLAYING != 0:
                Track_Flags |= PLAYBACK_EXTEND # ??? 0819b852 why does it do this
            Track_Flags = 0
            
            finish = 255
            if playing:
                PCM_Flags |= 0x40 # TODO: not actually what it does
                adsrtype = 3
            
        case _:
            if byte < 0xE0:
                # TODO: remove this after flags and IRAM are working
                if not Track_Flags & PLAYBACK_EXTEND:
                    if not pulse:
                        wavesample = 0
                    playing_start()
                #
                
                note = int.from_bytes(rom.read(1), 'little')
                Track_Note = note & 0x7F
                
                if Track_Flags & PLAYBACK_EXTEND == 0:
                    if Track_Flags & PLAYBACK_UNK0800 != 0:
                        Track_Flags &= PLAYBACK_UNK1000 | PLAYBACK_UNK2000
                        Track_Unk17 = Track_Unk16
                    if Track_Flags & PLAYBACK_UNK0100 != 0:
                        Track_Flags &= PLAYBACK_UNK0200 | PLAYBACK_UNK0400
                        Track_Unk1B = Track_Unk1A
                    set_pitch()
                    set_instrument()
                    Track_Flags |= PLAYBACK_PLAYING
                else:
                    set_pitch()
                    Track_Flags &= ~PLAYBACK_EXTEND
                
                if byte != 0:
                    if note & 0x80 != 0:
                        Track_Flags |= PLAYBACK_UNK0020
                    Track_Wait = byte
                else:
                    Track_Flags |= PLAYBACK_EXTEND
                    if note & 0x80 != 0:
                        Track_Wait = int.from_bytes(rom.read(1), 'little')
                
                play_note()
    offset = rom.tell()

def get_sample(wave, sample, volume):
    return (wave[sample] - 0x80) * volume

def sample_pitch(note):
    global samplerate
    
    pitch = note + PCM_Pitch / 256
    
    samplerate = waverate * (2 ** ((pitch - 60)/12))

def play_note():
    load_wave(PCM_Sample)
    
    if PCM_Unpitched:
        sample_pitch(60)
    else:
        sample_pitch(PCM_Note)

# based on 0x0819a2f0
def calculate_adsr():
    global playing
    global adsrtype
    global adsrFrameCounter
    
    global PCM_Flags
    global PCM_ADSR
    
    if not pulse: # TODO: check code, MAYBE pulse doesnt get tied to framerate?
        if PCM_Flags != 0x00:
            if PCM_Flags == 0x80:
                PCM_ADSR = PCM_Attack
                PCM_Flags += 1
            else:
                adsrBackup = PCM_ADSR
                if PCM_Flags == 0x81:
                    PCM_ADSR += PCM_Attack
                    if PCM_ADSR >= 255:
                        PCM_ADSR = 255
                        PCM_Flags += 1
                    return
                if PCM_Flags == 0x82:
                    PCM_ADSR -= PCM_Decay
                    if adsrBackup >= PCM_Decay or PCM_Sustain > 128:
                        PCM_ADSR = PCM_Sustain
                    return
                if PCM_Flags != 0x83:
                    PCM_ADSR -= PCM_Release
                    if adsrBackup < PCM_Release or PCM_ADSR == 0:
                        PCM_Flags = 0x00
                    return
    else: # TODO: find pulse adsr code
        if adsrtype == 0:
            if PCM_Attack == 255:
                PCM_ADSR = 255
                adsrtype += 1
            else:
                PCM_ADSR += adsr_formula(PCM_Attack)
                if PCM_ADSR >= 255:
                    PCM_ADSR = 255
                    adsrtype += 1
                    return
        if adsrtype == 1 and PCM_Decay < 255: # sustain ONLY works if decay is active
            PCM_ADSR -= adsr_formula(PCM_Decay)
            if PCM_ADSR <= PCM_Sustain:
                PCM_ADSR = PCM_Sustain
                return
        if adsrtype == 2:
            PCM_ADSR == PCM_Sustain
        if adsrtype == 3:
            if PCM_Release == 255:
                playing_stop()
                return
            else:
                PCM_ADSR -= adsr_formula(PCM_Release)
                if PCM_ADSR <= 0:
                    playing_stop()
                    return

def adsr_formula(value):
    return (value / outrate / (Track_Volume / 1024)) * 1024

def playing_start(): # TODO: figure out how this works and what it sets
    global playing
    global adsrtype
    
    global PCM_Flags
    global PCM_ADSR
    
    PCM_Flags = 0x80
    playing = 1
    PCM_ADSR = 0
    adsrtype = 0

def playing_stop(): # TODO: figure out how this works and what it sets
    global playing
    global adsrtype
    
    global PCM_Flags
    global PCM_ADSR
    
    PCM_Flags = 0x00
    playing = 0
    PCM_ADSR = 0
    adsrtype = 4

def load_wave(id):
    global wavehasloop
    global waverate
    global waveloop
    global wavelength
    global wave
    
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
    
    rom.seek(temp)

def should_render():
    return (finish < loopCount or maxxed < 1 or (finish == 255 and ((pulse and adsrtype != 4) or (not pulse and PCM_Flags != 0x00))))

def render(track):
    global samplerate
    global currentsample
    global wavesample
    global finish
    global offset
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
    
    global Track_Flags
    global Track_BPM
    global Track_Unk03
    global Track_ChannelStart
    global Track_ChannelOffset
    global Track_Wait
    global Track_Note
    global Track_Instrument
    global Track_Volume
    global Track_Pan
    global Track_PitchRange
    global Track_PitchAmount
    global Track_Unk11
    global Track_Channel
    global Track_Unk13
    global Track_Unk14
    global Track_Unk15
    global Track_Unk16
    global Track_Unk17
    global Track_Unk18
    global Track_Unk19
    global Track_Unk1A
    global Track_Unk1B
    global Track_Unk1C
    global Track_Unk1D
    global Track_Unk1E
    global Track_Unk1F
    
    global PCM_Flags
    global PCM_ADSR
    global PCM_Sample
    global PCM_Unpitched
    global PCM_SamplePlayback
    global PCM_VolumeRight
    global PCM_VolumeLeft
    global PCM_Pitch
    global PCM_Note
    global PCM_Attack
    global PCM_Decay
    global PCM_Sustain
    global PCM_Release
    
    global PSG_Attack
    global PSG_Decay
    global PSG_Sustain
    global PSG_Release
    global PSG_Unk4
    global PSG_Unk5
    global PSG_Wave
    global PSG_Unk7
    global PSG_Unk8
    global PSG_Unk9
    global PSG_UnkA
    global PSG_UnkB
    
    global REG_SOUNDCNT_L
    
    rom.seek(offset + (track * 2))
    offset += int.from_bytes(rom.read(2), 'little')
    rom.seek(offset)
    
    out = []
    wavesample = 0
    currentsample = 0
    finish = 0
    
    playing_stop()
    
    pulse = channel > 7
    
    maxxed = 0
    
    init_eram()
    
    # zero
    PCM_Flags = 0
    PCM_ADSR = 0
    PCM_Sample = 0
    PCM_Unpitched = 0
    PCM_SamplePlayback = 0
    PCM_VolumeRight = 0
    PCM_VolumeLeft = 0
    PCM_Pitch = 0
    PCM_Note = 0
    PCM_Attack = 0
    PCM_Decay = 0
    PCM_Sustain = 0
    PCM_Release = 0
    
    # zero
    PSG_Attack = 0
    PSG_Decay = 0
    PSG_Sustain = 0
    PSG_Release = 0
    PSG_Unk4 = 0
    PSG_Unk5 = 0
    PSG_Wave = 0
    PSG_Unk7 = 0
    PSG_Unk8 = 0
    PSG_Unk9 = 0
    PSG_UnkA = 0
    PSG_UnkB = 0
    
    leftover = 0
    
    pulse_rerender = (1 + pulse * (upsample - 1))
    pcm_rerender = (1 + (1 - pulse) * (upsample - 1))
    
    while should_render():
        renderTime = currentsample / (samplesPerFrame * 60)
        
        if renderTime % 10 == 0:
            print(f'{songIndex} {channel}: Rendering... {int(renderTime)} seconds')
        
        while Track_Wait <= 0 and finish < 255:
            read_song()
        
        Track_Wait += leftover
        leftover = 0
        Track_Wait -= Track_BPM / (1.25 * expectedFramerate)
        if Track_Wait < 0:
            leftover = Track_Wait
        
        # TODO: figure out when these are set
        if PCM_Flags >= 0x80 and PCM_Flags <= 0x83:
            #set_pitch()
            set_volume()
            #if pulse: set_pan()
        
        calculate_adsr()
        
        if not should_render():
            break
        
        if adsrtype != 4 and PCM_Flags & 0x80:
            for _ in range(round(samplesPerFrame) * pulse_rerender):
                sampleL = get_sample(wave, int(wavesample), (PCM_VolumeLeft / 256) * (PCM_ADSR / 256))
                sampleR = get_sample(wave, int(wavesample), (PCM_VolumeRight / 256) * (PCM_ADSR / 256))
                out.extend([int(sampleL * 256), int(sampleR * 256)] * pcm_rerender)
                
                wavesample += (samplerate / outrate) / pulse_rerender
                
                if wavesample >= len(wave):
                    if not wavehasloop:
                        playing_stop()
                    wavesample = waveloop + (wavesample % 1)
        else:
            out.extend([0, 0] * samplesPerFrame * upsample)
        
        currentsample += samplesPerFrame
        
        if currentsample >= endsample:
            maxxed = 1
            endsample = currentsample
        
    return out

with open(f'{input("rom: ")}.gba', 'rb') as rom:
    songtable = 0x21CB70
    instrumenttable = 0x21D1CC
    wavetable = 0xA806B8
    
    #songtable = 0x116BA0
    #instrumenttable = 0x116E54
    #wavetable = 0x5C6730
    
    songIndex = int(input("Song index: "))
    songCount = int(input("How many songs to export: "))
    loopCount = int(input("Loop count: "))
    
    for i in range(songCount):
        global endsample
        endsample = 0
        prevmax = 0
        
        rom.seek(songtable + (songIndex * 4))
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
                track += 1
                
                global offset
                offset = song
                
                rendered = render(track)
                
                if endsample > prevmax:
                    prevmax = endsample
                    if track > 1:
                        retry = 1
                        print('\nRETRYING: Underestimated length...\n')
                        break
                
                print('DONE\n')
                
                with open(f'{songIndex}_{channel}.wav', 'wb') as out:
                    out.write('RIFF'.encode('ascii'))
                    out.write((len(rendered) * 2 + 36).to_bytes(4, 'little')) # riff size
                    out.write('WAVEfmt '.encode('ascii'))
                    out.write((16).to_bytes(4, 'little')) # fmt size
                    out.write((1).to_bytes(2, 'little')) # type
                    out.write((2).to_bytes(2, 'little')) # channels
                    out.write((outrate * upsample).to_bytes(4, 'little')) # sample rate
                    out.write((outrate * upsample * 2 * 2).to_bytes(4, 'little')) # sample rate * bytes * channels
                    out.write((2 * 2).to_bytes(2, 'little')) # bytes * channels
                    out.write((16).to_bytes(2, 'little')) # bits
                    
                    out.write('data'.encode('ascii'))
                    out.write((len(rendered) * 2).to_bytes(4, 'little')) # data size
                    out.write(np.array(rendered, np.int16))
                
            if retry == 0:
                songIndex += 1
