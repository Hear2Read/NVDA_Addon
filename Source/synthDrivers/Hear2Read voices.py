# -*- coding: UTF-8 -*-
#synthDrivers/Hear2Read voices.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2007-2019 NV Access Limited, Peter Vágner, Aleksey Sadovoy, Leonard de Ruijter
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import os
from collections import OrderedDict
from . import _H2R_Speak
import threading
import languageHandler
from synthDriverHandler import SynthDriver, VoiceInfo, synthIndexReached, synthDoneSpeaking
import speech
# import globalVars
from logHandler import log

from speech.commands import (
	IndexCommand,
	CharacterModeCommand,
	LangChangeCommand,
	BreakCommand,
	PitchCommand,
	RateCommand,
	VolumeCommand,
	PhonemeCommand,
)

#error codes
EE_OK=0
EE_INTERNAL_ERROR=-1
EE_BUFFER_FULL=1
EE_NOT_FOUND=2

class SynthDriver(SynthDriver):
	name = "Hear2Read voices"
	description = "Hear2Read voices"

	supportedSettings=(
		SynthDriver.VoiceSetting(),
#		SynthDriver.VariantSetting(),
		SynthDriver.RateSetting(),
#		SynthDriver.RateBoostSetting(),
#		SynthDriver.PitchSetting(),
#		SynthDriver.InflectionSetting(),
		SynthDriver.VolumeSetting(),
	)
	supportedCommands = {
		IndexCommand,
		CharacterModeCommand,
		LangChangeCommand,
#		BreakCommand,
#		PitchCommand,
		RateCommand,
		VolumeCommand,
#		PhonemeCommand,
	}
	supportedNotifications = {synthIndexReached, synthDoneSpeaking}

	@classmethod
	def check(cls):
		return True

	def __init__(self):
#		log.info("H2R: Init function called")
		_H2R_Speak.initialize(self._onIndexReached)
		_H2R_Speak.getAvailableLanguages()
#		log.info("Using Hear2Read voices version %s" % _H2R_Speak.info())
#		log.info("Calling languageHandler.getLanguage()")
		lang=languageHandler.getLanguage()
#		log.info("Calling _H2R_Speak.setVoiceByLanguage(" + lang + ")")
		_H2R_Speak.setVoiceByLanguage(lang)
		self._language=lang
#		self._variantDict=_H2R_Speak.getVariantDict()
#		self.variant="max"
		self.rate=30
		self.pitch=40
		self.inflection=75
		if self.volume < 10: 
			log.info("H2R Init volume equaled 0 setting to 50%")
			self.volume = round(50*.8)
			_H2R_Speak.setParameter(_H2R_Speak.H2R_SpeakVOLUME,self.volume,0)

	def _get_language(self):
		return self._language

	PROSODY_ATTRS = {
		PitchCommand: "pitch",
		VolumeCommand: "volume",
		RateCommand: "rate",
	}

	IPA_TO_H2R_Speak = {
		u"θ": u"T",
		u"s": u"s",
		u"ˈ": u"'",
	}

	def _processText(self, text):
		# We need to make several replacements.
#		return text.translate({
#			0x1: None, # used for embedded commands
#			0x3C: u"&lt;", # <: because of XML
#			0x3E: u"&gt;", # >: because of XML
#			0x5B: u" [", # [: [[ indicates phonemes
#		})
		return(text)

	def speak(self,speechSequence):
		defaultLanguage=self._language
		textList=[]
		langChanged=False
		prosody={}
		# We output malformed XML, as we might close an outer tag after opening an inner one; e.g.
		# <voice><prosody></voice></prosody>.
		# However, H2R_Speak doesn't seem to mind.
		log.info("[TRW] Hear2Read voices.speak: Entered speak routine. _language = %s", self._language)
		for item in speechSequence:
#			log.info("Hear2Read voices speak fetching Item from speechSequence")
			if isinstance(item,str):
				log.info("\t[TRW] item is text = \"" + item + "\" calling _H2R_Speak.speak")
				_H2R_Speak.speak(item)
#				textList.append(self._processText(item))
			elif isinstance(item, IndexCommand):
				log.info("\t[TRW] item is IndexCommand = %d. calling _H2R_SPeak.sendIndex", item.index)
				_H2R_Speak.sendIndex(item.index)
#				textList.append("<mark name=\"%d\" />"%item.index)
			elif isinstance(item, CharacterModeCommand):
				log.info("\t[TRW] item  is CharacterModeCommand = " + str(item.state))
#				textList.append("<say-as interpret-as=\"characters\">" if item.state else "</say-as>")
			elif isinstance(item, LangChangeCommand):
				log.info("\t[TRW] item  is LangChangeCommand item.lang = %s", item.lang)
				lang_array = (item.lang).split('_') # for now ignore variant
				item.lang = lang_array[0]
				if ( item.lang != self._language ):
					log.info("\tLanguage is to be changed.  Calling _H2R_Speak.setVoiceAndVariant")
					# queue up a language change to happen at the correct time
					_H2R_Speak.setVoiceAndVariant(item.lang, None)
					self._language = item.lang
			elif isinstance(item, BreakCommand):
				log.info("\titem  is BreakCommand")
#				textList.append('<break time="%dms" />' % item.time)
			elif type(item) in self.PROSODY_ATTRS:
				log.info("\t[TRW] item  is in self.PROSODY_ATTRS %s", item)
#				if prosody:
#					# Close previous prosody tag.
#					textList.append("</prosody>")
#				attr=self.PROSODY_ATTRS[type(item)]
#				if item.multiplier==1:
#					# Returning to normal.
#					try:
#						del prosody[attr]
#					except KeyError:
#						pass
#				else:
#					prosody[attr]=int(item.multiplier* 100)
#				if not prosody:
#					continue
#				textList.append("<prosody")
#				for attr,val in prosody.items():
#					textList.append(' %s="%d%%"'%(attr,val))
#				textList.append(">")
			elif isinstance(item, PhonemeCommand):
				log.info("\t[TRW] item  is PhonemeCommand")
#				# We can't use str.translate because we want to reject unknown characters.
#				try:
#					phonemes="".join([self.IPA_TO_H2R_SPEAK[char] for char in item.ipa])
#					# There needs to be a space after the phoneme command.
#					# Otherwise, eSpeak will announce a subsequent SSML tag instead of processing it.
#					textList.append(u"[[%s]] "%phonemes)
#				except KeyError:
#					log.debugWarning("Unknown character in IPA string: %s"%item.ipa)
#					if item.text:
#						textList.append(self._processText(item.text))
			else:
				log.error("Unknown speech: %s"%item)
		# Close any open tags.
#		if langChanged:
#			textList.append("</voice>")
#		if prosody:
#			textList.append("</prosody>")
		text=u"".join(textList)
		if (text != ""):
			log.info("Hear2Read voices Speak: sending string to _H2R_Speak.speak(text): " + text)
			_H2R_Speak.speak(text)

	def cancel(self):
		log.info("[TRW] Hear2Read voices cancel entered")
		_H2R_Speak.stop()

	def pause(self,switch):
		log.info(" Hear2Read voices pause: switch = %d", switch)
		_H2R_Speak.pause(switch)

#	_rateBoost = False
#	RATE_BOOST_MULTIPLIER = 3

#	def _get_rateBoost(self):
#		return self._rateBoost

#	def _set_rateBoost(self, enable):
#		if enable == self._rateBoost:
#			return
#		rate = self.rate
#		self._rateBoost = enable
#		self.rate = rate

	def _get_rate(self):
		log.info("Hear2Read voices._get_rate called")
		val=_H2R_Speak.getParameter(_H2R_Speak.H2R_SpeakRATE,1)
#		if self._rateBoost:
#			val=int(val/self.RATE_BOOST_MULTIPLIER)
		return (val)

	def _set_rate(self,rate):
#		NVDA sends a rate between 0 and 100
		log.info("Hear2Read voices._set_rate called.  Rate = %d", rate)
#		val=self._percentToParam(rate, _H2R_Speak.minRate, _H2R_Speak.maxRate)
		val = rate
#		if self._rateBoost:
#			val=int(val*self.RATE_BOOST_MULTIPLIER)
#		log.info("Hear2Read voices._set_rate calling setParameter: val = %d", val)
		_H2R_Speak.setParameter(_H2R_Speak.H2R_SpeakRATE,val,0)

	def _get_pitch(self):
		val=_H2R_Speak.getParameter(_H2R_Speak.H2R_SpeakPITCH,1)
		return self._paramToPercent(val,_H2R_Speak.minPitch,_H2R_Speak.maxPitch)

	def _set_pitch(self,pitch):
		val=self._percentToParam(pitch, _H2R_Speak.minPitch, _H2R_Speak.maxPitch)
		_H2R_Speak.setParameter(_H2R_Speak.H2R_SpeakPITCH,val,0)

	def _get_inflection(self):
		val=_H2R_Speak.getParameter(_H2R_Speak.H2R_SpeakRANGE,1)
		return self._paramToPercent(val,_H2R_Speak.minPitch,_H2R_Speak.maxPitch)

	def _set_inflection(self,val):
		val=self._percentToParam(val, _H2R_Speak.minPitch, _H2R_Speak.maxPitch)
		_H2R_Speak.setParameter(_H2R_Speak.H2R_SpeakRANGE,val,0)

	def _get_volume(self):
		volume = round(_H2R_Speak.getParameter(_H2R_Speak.H2R_SpeakVOLUME,1)/.8)
		log.info("Hear2Read voices._get_volume called. volume = %d", volume)
		return volume

	def _set_volume(self,volume):
		log.info("Hear2Read voices._set_volume called volume = %d", volume)
		_H2R_Speak.setParameter( _H2R_Speak.H2R_SpeakVOLUME, round(volume*.8), 0 )

	def _getAvailableVoices(self):
		voices=OrderedDict()
		pathName = os.path.join(os.environ['ALLUSERSPROFILE'], "Hear2Read", "Languages")
		#list all files in Language directory
		list = os.listdir(pathName)
		for flitevoxFileName in list:
			list = flitevoxFileName.split("_")
			if list[0] == "H2R" or list[0] == "H2Rplay":
				temp = list[3].split('.')
				list[3] = temp[0]
#				log.info("Hear2Read voices _getAvailableVoices: flitevoxFilename = %s VoiceInfo = %s, %s, %s", flitevoxFileName, list[1], list[2], list[1])
				voices[list[1]] = VoiceInfo(list[1], list[2] + ' ' + list[3], list[1])
				log.info("Hear2Read voices _getAvailableVoices: Added voice " + list[1] + " " + list[2] + " " + list[1])
		return voices

	def _get_voice(self):
		curVoice=getattr(self,'_voice',None)
#		log.info("Hear2Read voices: _get_voice called:curVoice = %s", curVoice)
		if curVoice: 
#			log.info("Hear2Read voices _get_Voice: returning curVoice = " + curVoice)
			return curVoice
		curVoice = _H2R_Speak.getCurrentVoice()
		if not curVoice:
			log.info("Hear2Read voices _get_Voice: returning None")
			return ""
		log.info("Hear2Read voices _get_Voice: returning new voice identifier = " + _H2R_Speak.decodeH2RSpeakString(curVoice.identifier))
		return _H2R_Speak.decodeH2RSpeakString(curVoice.identifier)

	def _set_voice(self, identifier):
		log.info("Hear2Read voices._set_voice: entered, identifier = %s", identifier)
		if not identifier:
			return
#		log.info("Hear2Read voices _set_voice: identifier = " + identifier)
		# #5783: For backwards compatibility, voice identifies should always be lowercase
		identifier=identifier.lower()
#		log.info("Hear2Read voices _set_voice: setting self._voice to " + identifier)
		self._voice = identifier
		self._variant = 0
		try:
			res = _H2R_Speak.setVoiceAndVariant(voice=identifier,variant=self._variant)
		except:
			self._voice=None
			raise
		self._language=super(SynthDriver,self).language
#		log.info("Hear2Read voices _set_voice: setting self._language to " + self._language)

	def _onIndexReached(self, index):
		if index is not None:
			log.info("Hear2Read voices._onIndexReached: Queueing synthIndexReached.notify, index = %d", index)
			_H2R_Speak._execWhenDone(synthIndexReached.notify, synth=self, index=index)
		else:
			log.info("Hear2Read voices._onIndexReached: Queueing synthDoneSpeaking.notify")
			_H2R_Speak._execWhenDone( synthDoneSpeaking.notify, synth=self)

	def terminate(self):
		_H2R_Speak.terminate()

	def _get_variant(self):
		return self._variant

	def _set_variant(self,val):
		log.info("Hear2Read voices:_get_variant - variant val = %s doing nothing THIS SHOULD CHANGE", val)
		return
#		self._variant = val if val in self._variantDict else "max"
#		_H2R_Speak.setVoiceAndVariant(variant=self._variant)

	def _getAvailableVariants(self):
		return OrderedDict((ID,VoiceInfo(ID, name)) for ID, name in self._variantDict.items())
