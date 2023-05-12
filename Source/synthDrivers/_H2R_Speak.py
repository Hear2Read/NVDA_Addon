# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2007-2020 NV Access Limited, Peter Vágner
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

import time
import nvwave
import threading
import queue
from ctypes import cdll
from ctypes import *
import config
# import globalVars
from logHandler import log
import os
import codecs

isSpeaking = False
onIndexReached = None
bgThread=None
bgQueue = None
player = None
H2R_SpeakDLL=None
#: Keeps count of the number of bytes pushed for the current utterance.
#: This is necessary because index positions are given as ms since the start of the utterance.
_numBytesPushed = 0

#Parameter bounds
minRate=80
maxRate=450
minPitch=0
maxPitch=99

#event types
H2R_SpeakEVENT_LIST_TERMINATED=0
H2R_SpeakEVENT_WORD=1
H2R_SpeakEVENT_SENTENCE=2
H2R_SpeakEVENT_MARK=3
H2R_SpeakEVENT_PLAY=4
H2R_SpeakEVENT_END=5
H2R_SpeakEVENT_MSG_TERMINATED=6
H2R_SpeakEVENT_PHONEME=7

#position types
POS_CHARACTER=1
POS_WORD=2
POS_SENTENCE=3

#output types
AUDIO_OUTPUT_PLAYBACK=0
AUDIO_OUTPUT_RETRIEVAL=1
AUDIO_OUTPUT_SYNCHRONOUS=2
AUDIO_OUTPUT_SYNCH_PLAYBACK=3

#synth flags
H2R_SpeakCHARS_AUTO=0
H2R_SpeakCHARS_UTF8=1
H2R_SpeakCHARS_8BIT=2
H2R_SpeakCHARS_WCHAR=3
H2R_SpeakSSML=0x10
H2R_SpeakPHONEMES=0x100
H2R_SpeakENDPAUSE=0x1000
H2R_SpeakKEEP_NAMEDATA=0x2000

#speech parameters
H2R_SpeakSILENCE=0
H2R_SpeakRATE=1
H2R_SpeakVOLUME=2
H2R_SpeakPITCH=3
H2R_SpeakRANGE=4
H2R_SpeakPUNCTUATION=5
H2R_SpeakCAPITALS=6
H2R_SpeakWORDGAP=7
H2R_SpeakOPTIONS=8   # reserved for misc. options.  not yet used
H2R_SpeakINTONATION=9
H2R_SpeakRESERVED1=10
H2R_SpeakRESERVED2=11

#error codes
EE_OK=0
EE_INTERNAL_ERROR=-1
EE_BUFFER_FULL=1
EE_NOT_FOUND=2

curr_vox = ""

# eSpeak initialization flags
H2R_SpeakINITIALIZE_DONT_EXIT = 0x8000

class H2R_Speak_EVENT_id(Union):
	_fields_=[
		('number',c_int),
		('name',c_char_p),
		('string',c_char*8),
	]

class H2R_Speak_EVENT(Structure):
	_fields_=[
		('type',c_int),
		('unique_identifier',c_uint),
		('text_position',c_int),
		('length',c_int),
		('audio_position',c_int),
		('sample',c_int),
		('user_data',c_void_p),
		('id',H2R_Speak_EVENT_id),
	]

class H2R_Speak_VOICE(Structure):
	_fields_=[
		('name',c_char_p),
		('languages',c_char_p),
		('identifier',c_char_p),
		('gender',c_byte),
		('age',c_byte),
		('variant',c_byte),
		('xx1',c_byte),
		('score',c_int),
		('spare',c_void_p),
	]

	def __eq__(self, other):
		return isinstance(other, type(self)) and addressof(self) == addressof(other)

	# As __eq__ was defined on this class, we must provide __hash__ to remain hashable.
	# The default hash implementation is fine for  our purposes.
	def __hash__(self):
		return super().__hash__()

H2R_curVoice = H2R_Speak_VOICE()

# constants that can be returned by H2R_Speak_callback
CALLBACK_CONTINUE_SYNTHESIS=0
CALLBACK_ABORT_SYNTHESIS=1

def encodeH2RSpeakString(text):
	return text.encode('utf8')

def decodeH2RSpeakString(data):
	return data.decode('utf8')

t_H2R_Speak_callback=CFUNCTYPE(c_int,POINTER(c_short), c_int, POINTER(H2R_Speak_EVENT))

@t_H2R_Speak_callback
def callback(wav, numsamples, event):
#	log.info("_H2R_Speak callback: Entered.  numsamples = %d", numsamples)
	try:
		global player, isSpeaking, _numBytesPushed
		if not isSpeaking:
#			log.info("_H2r_Speak callback: isSpeaking is False returning CALLBACK_ABORT_SYNTHESIS")
			player.stop()
			return CALLBACK_ABORT_SYNTHESIS
#			isSpeaking = True
		indexes = []
#		log.info("_H2R_Speak callback looking at events")
		for e in event:
			log.info("_H2R_Speak callback: event")
			if e.type==H2R_SpeakEVENT_MARK:
				log.info("H2R_SpeakEVENT_MARK found")
				indexNum = int(decodeH2RSpeakString(e.id.name))
				log.info("+_H2R_SpeakEVENT indexNum = %d", indexNum)
				# e.audio_position is ms since the start of this utterance.
				# Convert to bytes since the start of the utterance.
				BYTES_PER_SAMPLE = 2
				MS_PER_SEC = 1000
				bytesPerMS = player.samplesPerSec * BYTES_PER_SAMPLE // MS_PER_SEC
				indexByte = e.audio_position * bytesPerMS
				# Subtract bytes in the utterance that have already been handled
				# to give us the byte offset into the samples for this callback.
				indexByte -= _numBytesPushed
				indexes.append((indexNum, indexByte))
			elif e.type==H2R_SpeakEVENT_LIST_TERMINATED:
#				log.info("H2R_SpeakEVENT_LIST_TERMINATED found")
				break
		if not wav:
			log.info("_H2r_Speak.callback: no wav file isSpeaking = False (end of text to speak)")
			isSpeaking = False
			player.idle()
			onIndexReached(None)
			return CALLBACK_ABORT_SYNTHESIS
#		temp = numsamples * sizeof(c_short)
#		if (temp != 320): log.info("_H2R_Speak callback: numSamples * sizeof(c_short) = %d", temp);
		wav = string_at(wav, numsamples * sizeof(c_short)) if numsamples>0 else b""
		prevByte = 0
		for indexNum, indexByte in indexes:
			log.info("_H2r_Speak callback: feeding player indexNum = %d, indexByte = %d", indexNum, indexByte)
			player.feed(wav[prevByte:indexByte],
				onDone=lambda indexNum=indexNum: onIndexReached(indexNum))
			prevByte = indexByte
			if not isSpeaking:
#				log.info("_H2R_Speak.callback: in loop not speaking CALLBACK_ABORT_SYNTHESIS")
				return CALLBACK_ABORT_SYNTHESIS
#		log.info("_H2r_Speak callback: FEEDING PLAYER")
		player.feed(wav[prevByte:])
		_numBytesPushed += len(wav)
#		log.info("_H2r_Speak callback: CALLBACK_CONTINUE_SYNTHESIS")
		return CALLBACK_CONTINUE_SYNTHESIS
	except:
		log.error("callback FAILED", exc_info=True)

class BgThread(threading.Thread):
	def __init__(self):
		super().__init__(name=f"{self.__class__.__module__}.{self.__class__.__qualname__}")
		self.setDaemon(True)

	def run(self):
#		global isSpeaking
		while True:
			func, args, kwargs = bgQueue.get()
			if not func:
				break
			try:
#				log.info("BgThread.run: calling queued function")
				func(*args, **kwargs)
			except:
				log.error("Error running function from queue", exc_info=True)
			bgQueue.task_done()

def _execWhenDone(func, *args, mustBeAsync=False, **kwargs):
	global bgQueue
	if mustBeAsync or bgQueue.unfinished_tasks != 0:
		# Either this operation must be asynchronous or There is still an operation in progress.
		# Therefore, run this asynchronously in the background thread.
		bgQueue.put((func, args, kwargs))
	else:
		func(*args, **kwargs)

def _speak(text):
	global isSpeaking, _numBytesPushed
	# if H2RSpeak was interupted while speaking ssml that changed parameters such as pitch,
	# It may not reset those runtime values back to the user-configured values.
	# Therefore forcefully cause eSpeak to reset its parameters each time beginning to speak again after not speaking. 
#	if not isSpeaking:
#		log.info("_Speak isSpeaking = false -- calling player.Stop()")
#		player.stop()
#		H2R_SpeakDLL.H2R_Speak_stop()
#	log.info("_Speak: isSpeaking = True sending text string = %s", text)
	isSpeaking = True
	_numBytesPushed = 0
	# eSpeak can only process compound emojis when using a UTF8 encoding
	text2=text.encode('utf8',errors='ignore')
#log.info("_speak calling H2R_SpeakDLL.H2R_Speak_synthesizeText(%s)", text)
	returncode = H2R_SpeakDLL.H2R_Speak_synthesizeText(text2)
	return returncode

def findNextTerminator(string, start):
	index = start
#	danda = hex(2404).encode()
	length = len(string)
#	log.info("_H2R_Speak.findNextTerminator: string length = %s", length)
	whitespace = { " ", "\r", "\t", "\n"  }
	while (index < len(string)) :
#		log.info("_H2R_Speak.findNextTerminator: char = %s", string[index])
		if (string[index] == "." or 
		    string[index] == "!" or
		    string[index] == "?" or
		    string[index] == "," or
		    string[index] == ";" or
		    ord(string[index]) == 0x0964) :
#			log.info("_H2R_Speak.findNextTerminator: found terminating char = %s", string[index])
			if (string[index + 1] in whitespace) : break
		index += 1

	if start == index : return 0
	return index

def speak(text):
	global bgQueue
#	log.info("_H2R_Speak speak() text = %s", text)
	# break text info individual sentences if necessary and send only 1 sentence at a time to DLL
	# end of sentence is period or denda
#	text=text.encode('utf8',errors='ignore')
	startIndex = 0
	index = findNextTerminator(text, startIndex)
#	log.info("_H2R_Speak.speak index = %d", index)
	i = 0
	while ( index != 0 and index <= len(text) ):
		sentence = text[startIndex : index + 1].strip()
		if sentence != "" :
#			log.info ("_H2R_Speak.speak queueing %s", sentence)
			_execWhenDone(_speak, sentence, mustBeAsync=True)
		startIndex = index + 1
#		log.info("_H2R_Speak.speak finding next sentence starting at index %s", startIndex)
		index = findNextTerminator(text, startIndex)
#		log.info("_H2R_Speak.speak index = %d", index)
	if startIndex < len(text) :
		sentence = text[startIndex : ].strip()
		if sentence != "" :
#			log.info ("_H2R_Speak.speak queueing %s", sentence)
			_execWhenDone(_speak, sentence, mustBeAsync=True)
	
def sendIndex(index):
	log.info("_H2R_Speak.sendIndex entered. index = %d calling onIndexReached", index)
	_execWhenDone( onIndexReached, index)

def stop():
	global isSpeaking, bgQueue
#	log.info("_H2R_Speak stop entered")
	# Kill all speech from now.
	# We still want parameter changes to occur, so requeue them.
	params = []
	try:
		while True:
			item = bgQueue.get_nowait()
			if item[0] != _speak:
				params.append(item)
			bgQueue.task_done()
	except queue.Empty:
		# Let the exception break us out of this loop, as queue.empty() is not reliable anyway.
		pass
	for item in params:
		bgQueue.put(item)
#	log.info("_H2R_Speak.stop Removed all text from bgQueue, setting isSpeaking = False and calling player.stop()")
	isSpeaking = False
#	H2R_SpeakDLL.H2R_Speak_stop();
	player.stop()

def pause(switch):
	global player
	player.pause(switch)

def setParameter(param,value,relative):
	log.info("_H2R_Speak.setParameter called param = %d value = %d  relative = %d", param, value, relative)
	_execWhenDone(H2R_SpeakDLL.H2R_Speak_SetParameter,param,value,relative)

def getParameter(param,current):
	log.info("_H2R_Speak.getParameter called. Param = %s current = %d", param, current)
	return H2R_SpeakDLL.H2R_Speak_GetParameter(param,current)

def getVoiceList():
	voices=H2R_SpeakDLL.H2R_Speak_ListVoices(None)
	voiceList=[]
	for voice in voices:
		if not voice: break
		voiceList.append(voice.contents)
	return voiceList

def getCurrentVoice():
#	log.info("_H2R getCurrentVoice: entered")
#	voice =  H2R_SpeakDLL.H2R_Speak_GetCurrentVoice()
	if H2R_curVoice.name != None:
#		log.info("_H2R getCurrentVoice returning H2R_curVoice.  Contents... name = " + decodeH2RSpeakString(H2R_curVoice.name) + " id = " + decodeH2RSpeakString(H2R_curVoice.identifier))
		return H2R_curVoice
	else:
#		log.info("_H2R getCurrentVoice returning None")
		return None

#def setVoice(voice):
#	# For some weird reason, H2R_Speak_EspeakSetVoiceByProperties throws an integer divide by zero exception.
#	log.info("_H2R setVoice: entered")
#	setVoiceByName(voice)

#def setVoiceByName(name):
#	log.info("_H2R setVoiceByName: entered")
#	_execWhenDone(H2R_SpeakDLL.H2R_Speak_SetVoice,encodeH2RSpeakString(name))

def _setVoiceAndVariant(voice=None, variant=None):
#	log.info("_H2R_Speak - setVoiceAndVariant: voice = %s variant = %s", voice, variant)
	v=getCurrentVoice()
	if (v == None): return EE_NOT_FOUND
	res = decodeH2RSpeakString(v.identifier).split("+")
	log.info("_H2R_Speak - setVoiceAndVariant: currentVoice = %s", res[0])
	if not voice:
		voice = res[0]
	if not variant:
		if len(res) == 2:
			variant = res[1]
		else:
			variant = ""
	log.info("_H2R _setVoiceAndVariant: entered  voice = " + voice + " variant = " + variant)
	return(setVoiceByLanguage(voice))


def setVoiceAndVariant(voice=None, variant=None):
#	log.info("_H2R setVoiceAndVariant: entered")
	_execWhenDone(_setVoiceAndVariant, voice=voice, variant=variant)

def getAvailableLanguages():
#	log.info("_H2R_Speak_getAvailableLanguages entered")
	pathName = os.path.join(os.environ['ALLUSERSPROFILE'], "Hear2Read", "Languages")
	#list all files in Language directory
	list = os.listdir(pathName)
	for file in list:
		parts = file.split("_")
		if parts[0] == "H2R" or parts[0] == "H2Rplay":
#			log.info("_H2R_Speak:getAvailableLanguages - found %s \n\tCalling H2R_SpeakDLL.H2R_Speak_Add_Voice",file)
			H2R_SpeakDLL.H2R_Speak_Add_Voice(encodeH2RSpeakString(parts[1]))
#	f = open (fileName)
#	for each line, see if the corresponding voice exists in the Hear2Read directory
#	for line in f:
#		list = line.split(":")
#		log.info("_H2R_Speak_setAvailableLanguages: found %s", list[0])
#		languageFile = 	os.path.join(globalVars.appDir, "..", "Hear2Read", "NVDA", "Languages",  ((list[4].rstrip('\r\n')) + ".flitevox"))
#		log.info("Checking %s", languageFile)
#		if (os.path.exists(languageFile)):
#			log.info("calling H2R_Speak_DLL.H2R_Speak_Add_VOice languageFile = %s", languageFile)
#			H2R_SpeakDLL.H2R_Speak_Add_Voice(encodeH2RSpeakString(list[0]))

def setVoiceByLanguage(lang):
#	log.info("_H2R_Speak_setVoiceByLanguage: entered. lang = " + lang)
	pathName = os.path.join(os.environ['ALLUSERSPROFILE'], "Hear2Read", "Languages")
	#Get all files in the Language Directory
	list = os.listdir(pathName)
	for fileName in list:
		parts = fileName.split("_")
		if parts[0] == "H2R" or parts[0] == "H2Rplay":
		# Found one of the NVDA Addon voice file
#			log.info("_H2R_Speak setVoiceByLanguage: parts = %s %s %s %s", parts[0], parts[1], parts[2], parts[3])
			if parts[1] == lang:
				fullPath = os.path.join(os.environ['ALLUSERSPROFILE'], "hear2read", "Languages", fileName)
				log.info("_H2R_Speak:setVoiceByLanguage - found %s for lang %s",fullPath, lang)
				hr = H2R_SpeakDLL.H2R_Speak_SetVoice(encodeH2RSpeakString(lang), encodeH2RSpeakString(fullPath))
				if (hr == EE_OK):
					# first fill in the H2R_curVoice Structure
					temp =  parts[3].split('.')
					parts[3] = temp[0]
					H2R_curVoice.name = encodeH2RSpeakString(parts[2] + " " +parts[3])
					H2R_curVoice.languages = encodeH2RSpeakString(parts[1])
					H2R_curVoice.identifier = encodeH2RSpeakString(parts[1])
					H2R_curVoice.age = 0
					if parts[3] == "Male":
						H2R_curVoice.gender = 1
						H2R_curVoice.variant = 1
					elif parts[3] == "Female":
						H2R_curVoice.gender = 2
						H2R_curVoice.varient = 2
					else:
						H2R_CurVoice.gender = 0
						H2R_curVoice.variant = 0
					log.info("_H2R_Speak setVoiceByLanguage: H2R_curVoice Set languages = " + decodeH2RSpeakString(H2R_curVoice.languages) + " name = " + decodeH2RSpeakString(H2R_curVoice.name) + " identifier = " + decodeH2RSpeakString(H2R_curVoice.identifier))
					return hr
				else:
					log.info("_H2R_Speak setVoiceByLanguage: returning %s", hr)
					return hr
	log.info("_H2R_Speak setVoiceByLanguage: Language " + lang + " not found.  Reverting to English")
	lang = "en"
	for fileName in list:
		parts = fileName.split("_")
		if parts[0] == "H2R" or parts[0] == "H2Rplay":
		# Found one of the NVDA Addon voice file
#			log.info("_H2R_Speak setVoiceByLanguage: parts = %s %s %s %s", parts[0], parts[1], parts[2], parts[3])
			if parts[1] == lang:
				fullPath = os.path.join(os.environ['ALLUSERSPROFILE'], "hear2read", "Languages", fileName)
				log.info("_H2R_Speak:setVoiceByLanguage - found %s for lang %s",fullPath, lang)
				hr = H2R_SpeakDLL.H2R_Speak_SetVoice(encodeH2RSpeakString(lang), encodeH2RSpeakString(fullPath))
				if (hr == EE_OK):
					# first fill in the H2R_curVoice Structure
					temp =  parts[3].split('.')
					parts[3] = temp[0]
					H2R_curVoice.name = encodeH2RSpeakString(parts[2] + " " +parts[3])
					H2R_curVoice.languages = encodeH2RSpeakString(parts[1])
					H2R_curVoice.identifier = encodeH2RSpeakString(parts[1])
					H2R_curVoice.age = 0
					if parts[3] == "Male":
						H2R_curVoice.gender = 1
						H2R_curVoice.variant = 1
					elif parts[3] == "Female":
						H2R_curVoice.gender = 2
						H2R_curVoice.varient = 2
					else:
						H2R_CurVoice.gender = 0
						H2R_curVoice.variant = 0
					log.info("_H2R_Speak setVoiceByLanguage: H2R_curVoice Set languages = " + decodeH2RSpeakString(H2R_curVoice.languages) + " name = " + decodeH2RSpeakString(H2R_curVoice.name) + " identifier = " + decodeH2RSpeakString(H2R_curVoice.identifier))
					return hr
				else:
					log.info("_H2R_Speak setVoiceByLanguage: returning %s", hr)
					return hr
	H2R_curVoice.name = None
	return EE_INTERNAL_ERROR
				
				
#	log.info("_H2R_Speak_setVoiceByLanguage: filename = " + fileName)
#	#open the language.dict file
#	f = open (fileName)
#	#for each line, see if the corresponding voice exists in the Hear2Read directory
#	for line in f:
#		list = line.split(":")
#		log.info("_H2R_Speak_setVoiceByLanguage: line = " + line + " list[0] = " + list[0])
#		if list[0] == lang:
#			#create the full file name of the corresponding .flitevox file
#			fname = (list[4].rstrip('\r\n')) + ".flitevox"
#			fileName = os.path.join(globalVars.appDir, "..", "hear2read", "NVDA", "Languages", fname)
#			log.info("_H2R_Speak_setVoiceByLanguage: flitevox filename = " + fileName)
#			if (os.path.exists(fileName)):
#				#tell dll to use the .flitevox file 
#				flitevoxFileName = fileName.encode('utf-8')
#				log.info("_H2R_Speak_setVoiceByLanguage: calling dll.H2R_Speak_SetVoice(" + lang +", " + fileName + ")")
#				hr = H2R_SpeakDLL.H2R_Speak_SetVoice(encodeH2RSpeakString(lang), encodeH2RSpeakString(fileName))
#				#if the dll returns successfully return success
#				if (hr == EE_OK):
#                   # first fill in the H2R_curVoice Structure
#					H2R_curVoice.name = encodeH2RSpeakString(list[1])
#					H2R_curVoice.languages = encodeH2RSpeakString(list[0])
#					H2R_curVoice.identifier = encodeH2RSpeakString(list[0])
#					if list[2] == "Male":
#						H2R_curVoice.gender = 1
##						H2R_curVoice.gender = 2
#					else:
#						H2R_CurVoice.gender = 0
#					H2R_curVoice.age = 0
#					H2R_curVoice.variant = 0
#					log.info("_H2R_Speak setVoiceByLanguage: H2R_curVoice Set languages = " + decodeH2RSpeakString(H2R_curVoice.languages) + " name = " + decodeH2RSpeakString(H2R_curVoice.name) + " identifier = " + decodeH2RSpeakString(H2R_curVoice.identifier))
#					return hr
#				else:
#					log.info("_H2R_Speak setVoiceByLanguage: returning %d", hr)
#					return hr
#	H2R_curVoice.name = None
#	return EE_INTERNAL_ERROR

#	v.languages=encodeH2RSpeakString(lang)
#	try:
#		H2R_SpeakDLL.H2R_Speak_SetVoiceByProperties(byref(v))
#	except:
#		v.languages=encodeH2RSpeakString("en")
#		H2R_SpeakDLL.H2R_Speak_SetVoiceByProperties(byref(v))

#def setVoiceByLanguage(lang):
#	log.info("_H2R _setVoiceByLanguage: entered.  lang = " + lang)
#	_execWhenDone(H2R_SpeakDLL.H2R_Speak_SetVoice, encodeH2RSpeakString(lang), encodeH2RSpeakString(""), encodeH2RSpeakString(""))

def H2R_Speak_errcheck(res, func, args):
	if res != EE_OK:
		log.info("_H2R H2R_Speak_errCheck: entered:  res = " + str(res))
		raise RuntimeError("%s: code %d" % (func.__name__, res))
	return res

def initialize(indexCallback=None):
	"""
	@param indexCallback: A function which is called when eSpeak reaches an index.
		It is called with one argument:
		the number of the index or C{None} when speech stops.
	"""
	log.info("_H2R_Speak initialize: entered")
	if (indexCallback != None): log.info("_H2R_Speak indexCallback not None")
	global H2R_SpeakDLL, bgThread, bgQueue, player, onIndexReached
	log.info("_H2R_Speak initialize:  H2R_SpeakDLL = " + os.path.join(os.environ['ALLUSERSPROFILE'], "Hear2Read",  "Hear2Read_addon_engine.dll"))
	H2R_SpeakDLL = cdll.LoadLibrary(os.path.join(os.environ['ALLUSERSPROFILE'], "Hear2Read",  "Hear2Read_addon_engine.dll"))
	H2R_SpeakDLL = cdll.LoadLibrary(os.path.join("C:/ProgramData",              "Hear2Read",  "Hear2Read_addon_engine.dll"))
	H2R_SpeakDLL.H2R_Speak_init.argtypes=(c_char_p,)
	H2R_SpeakDLL.H2R_Speak_init.errcheck=H2R_Speak_errcheck
	H2R_SpeakDLL.H2R_Speak_SetVoice.argtypes=(c_char_p, c_char_p,)
	H2R_SpeakDLL.H2R_Speak_SetVoice.errcheck=H2R_Speak_errcheck
	H2R_SpeakDLL.H2R_Speak_Add_Voice.argtypes=(c_char_p,)
#	H2R_SpeakDLL.UNREGISTER_VOXrestype=c_char_p
#	H2R_SpeakDLL.REGISTER_VOX.errcheck=H2R_Speak_errCheck
#	H2R_SpeakDLL.H2R_Speak_SetVoiceByLanguage.errcheck=H2R_Speak_errcheck 
#	H2R_SpeakDLL.H2R_Speak_Info.restype=c_char_p
	H2R_SpeakDLL.H2R_Speak_synthesizeText.errcheck=H2R_Speak_errcheck
	H2R_SpeakDLL.H2R_Speak_synthesizeText.argtypes=(c_char_p,)
#	H2R_SpeakDLL.H2R_Speak_SetVoiceByName.errcheck=H2R_Speak_errcheck
#	H2R_SpeakDLL.H2R_Speak_SetVoiceByName.argtypes=(c_char_p,)
#	H2R_SpeakDLL.H2R_Speak_SetSynthCallback.errcheck=H2R_Speak_errcheck
#	H2R_SpeakDLL.H2R_Speak_SetSynthCallback.argtypes= (c_char_p,)
#	H2R_SpeakDLL.H2R_Speak_SetVoiceByProperties.errcheck=H2R_Speak_errcheck
	H2R_SpeakDLL.H2R_Speak_SetParameter.argtypes=(c_int, c_int, c_int,)
	H2R_SpeakDLL.H2R_Speak_SetParameter.errcheck=H2R_Speak_errcheck
	H2R_SpeakDLL.H2R_Speak_GetParameter.argtypes=(c_int, c_int,)
	H2R_SpeakDLL.H2R_Speak_GetParameter.restype=c_int
	
#	H2R_SpeakDLL.H2R_Speak_Terminate.errcheck=H2R_Speak_errcheck
#	H2R_SpeakDLL.H2R_Speak_ListVoices.restype=POINTER(POINTER(H2R_Speak_VOICE))
	
#	H2R_SpeakDLL.H2R_Speak_GetCurrentVoice.restype=POINTER(H2R_Speak_VOICE)
	H2R_SpeakPath = os.path.join(os.environ['ALLUSERSPROFILE'], "Hear2Read", "Languages")
		
	log.info("_H2R_Speak: H2R_SpeakPath = " + H2R_SpeakPath + " calling H2R_SpeakDLL.H2R_Speak_init")
	H2R_SpeakDLL.H2R_Speak_init(encodeH2RSpeakString(H2R_SpeakPath), callback)
	
	player = nvwave.WavePlayer(channels=1, samplesPerSec=16000, bitsPerSample=16, outputDevice=config.conf["speech"]["outputDevice"], buffered=True)
	onIndexReached = indexCallback
#	H2R_SpeakDLL.H2R_Speak_SetSynthCallback(callback)
	bgQueue = queue.Queue()
	bgThread=BgThread()
	bgThread.start()


def terminate():
	global bgThread, bgQueue, player, H2R_SpeakDLL , onIndexReached
	log.info("_H2R_Speak terminate entered")
	stop()
	bgQueue.put((None, None, None))
	bgThread.join()
	H2R_SpeakDLL.H2R_Speak_Terminate()
	bgThread=None
	bgQueue=None
	player.close()
	player=None
	H2R_SpeakDLL=None
	onIndexReached = None

def info():
	# Python 3.8: a path string must be specified, a NULL is fine when what we need is version string.
	return H2R_SpeakDLL.H2R_Speak_Info(None)

def getVariantDict():
#	dir = os.path.join(globalVars.appDir, "synthDrivers", "H2R_Speak-data", "voices", "!v")
	# Translators: name of the default H2R_Speak varient.
	variantDict={"none": pgettext("H2R_SpeakVarient", "none")}
#	log.info("_H2R_Speak: getVariantDict returning variantDict[none] = " + variantDict["none"])
	return(variantDict)
#	for fileName in os.listdir(dir):
#		absFilePath = os.path.join(dir, fileName)
#		if os.path.isfile(absFilePath):
#			# In python 3, open assumes the default system encoding by default.
#			# This fails if Windows' "use Unicode UTF-8 for worldwide language support" option is enabled.
#			# The expected encoding is unknown, therefore use latin-1 to stay as close to Python 2 behavior as possible.
#			try:
#				with open(absFilePath, 'r', encoding="latin-1") as file:
#					for line in file:
#						if line.startswith('name '):
#							temp=line.split(" ")
#							if len(temp) ==2:
#								name=temp[1].rstrip()
#								break
#						name=None
#			except:
#				log.error("Couldn't parse H2R_Speak variant file %s" % fileName, exc_info=True)
#				continue
#		if name is not None:
#			variantDict[fileName]=name
#	return variantDict

