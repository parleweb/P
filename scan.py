"""
Parladata
scan.py
"""

# IMPORT
import sys
import os
import datetime
import logging

from jinja2 import Environment, PackageLoader, select_autoescape, FileSystemLoader, TemplateNotFound, TemplateSyntaxError, UndefinedError
import markdown2
import json
import csv
from pprint import pprint

# parladata package
from .log import logger
from .misc import plw_get_url


#
# Generate Index files
#
class PlwScan(object):
	def __init__(self, outpath=''):
		self.static_idx_path = outpath

		self.routeidx = {}
		self.routeidxname = ""
		self.routeisopen = False

	def __del__(self):
		pass

	def openidx(self, name):
		if( self.routeisopen == True ):
			#logger.info("SCAN is opened - skip or need to close first")
			return False
		self.routeisopen = True
		self.routeidxname = name
		#logger.info("IDX OPEN for "+name)
		return True

	def closeidx(self):
		if( self.routeisopen == False ):
			#logger.info("SCAN not opened - skip")
			return False
		logger.info("IDX "+self.routeidxname+ " has "+str(len(self.routeidx)))
		print(self.routeidx)
		return True

	def addidx(self, plwd):
		if( self.routeisopen == False ):
			#logger.info("SCAN not opened - skip")
			return False

		info = {}
		url = plwd['sourceurl']
		#print(plwd)
		#print(type(plwd))

		info['sourceurl'] = plwd['sourceurl']
		try:
			info['pagetitle'] = plwd['pagetitle']
		except:
			info['pagetitle'] = 'no title'
		try:
			info['pagedescription'] = plwd['pagedescription']
		except:
			info['pagedescription'] = 'no description'
		self.routeidx[url] = info
		print(self.routeidx)

		return True


	def scan(self, sourcedir, scanfor = '', jsonfile = "idx.json"):
		logger.info("IDX SCAN source %s for %s" %(sourcedir, scanfor))
		try:
			for dirnum, (dirpath, dirs, files) in enumerate(os.walk(sourcedir)):

				nbgeneration = dirpath.count('\\')

				# root
				if( dirnum == 0):
					self.idxroot = dirpath
					self.idxgeneration = nbgeneration
					self.generation = 0
					self.parent = 0
					self.idx = self.idxroot
					self.scanid = []
					self.lenidbefore = 0
					self.countid = 1
					self.tochtml = []
					self.toclist = {}
				else:
				# parent and child numerotation into list scanid as [1, 1, 2, 1...]
					if( self.parent != nbgeneration ):
						if( nbgeneration < self.parent ):
							# previous generation
							idtoremove = self.parent-nbgeneration
							del self.scanid[-idtoremove:]
							self.countid = self.scanid[-1] + 1
							self.scanid[-1] = self.countid
						else:
							# new generation
							self.countid = 1
							self.scanid.append(self.countid)
						self.parent = nbgeneration
					else:
						self.countid += 1
						if len(self.scanid) > 1:
							self.scanid[-1] = self.countid
						else:
							self.scanid.append(self.countid)

					self.generation = nbgeneration
					self.idx = dirpath.split(self.idxroot+'\\')[-1].split('\\')[-1]
					self.curdirnum = dirnum

					# add to scan memory the directory

					if( len(files) > 0 ):
						self.scandir(dirpath, dirs, files)
						# just pure number without .
						self.lenidbefore = len(''.join(map(str, self.scanid)))
						if( scanfor != '' ):
							tocid = '.'.join(map(str, self.scanid))
							logger.debug("SCAN "+tocid+" FOR "+scanfor)
							i = 1
							self.toclist[tocid]['scan'] = {}
							for filename in files:
								if i > 1:
									#self.countid += 1
									#self.scanid.append(self.countid)
									#tocid = '.'.join(map(str, self.scanid))
									logger.debug("SCAN ADD "+tocid+" FOR "+scanfor)
								ok = self.scanfile(tocid, scanfor, dirpath, filename, i)
								if( ok == True ):
									i += 1
								else:
									logger.critical("error walking file : "+filename)
									return ''

		except ValueError as e:
			logger.critical("error walking dir : "+sourcedir+" "+str(e))
			return ''

		# make deep to close and open <ul> analyse
		lastdeep = 1
		for keyid, data in reversed(sorted(self.toclist.items())):
			closelevel = data['deepbefore'] - data['deep']
			if( closelevel < 0 ):
				closelevel = 0
			if( data['deep'] > data['deepbefore'] ):
				openlevel = 1
			if( lastdeep > data['deep'] ):
				openlevel = 1
			else:
				openlevel = 0
			if( data['deep'] == lastdeep ):
				samelevel = 1
			else:
				samelevel = 0
			logger.info( 'deep %d before %d lastdeep %d close %d open %d same %d - %s' %(data['deep'], data['deepbefore'], lastdeep, closelevel, openlevel, samelevel, keyid))
			data['deepopen'] = openlevel
			data['deepclose'] = closelevel
			data['deepsame'] = samelevel
			lastdeep = data['deep']

		# write json
		#self.htmldir()
		if jsonfile.find('.json') == -1:
			jsonfile += '.json'
		self.jsondir(jsonfile)
		return jsonfile


	def htmldir(self):
		logger.debug("HTML")
		logger.debug(self.tochtml)

	def jsondir(self, fout):
		logger.debug("JSON")
		#logger.info("toclist 2 " + str(self.toclist['2']))
		data = self.toclist
		#data = json.dumps(self.toclist, indent=4, sort_keys=True)
		logger.debug("JSON DUMP")
		logger.debug(data)
		#pprint(data)
		try:
			myFile = open(fout, "w", encoding='utf-8')
		except FileNotFoundError as e:
			getdir = os.path.dirname(fout)
			logger.info("create directory "+getdir+" from "+fout)
			try:
				os.mkdir(getdir, 0o777)
				myFile = open(fout, "w", encoding='utf-8')
			except FileNotFoundError as e:
				logger.critical("impossible to use file "+fout)
				return False
			#
			# more error check to add
			#
		try:
			json.dump(data, myFile, indent=4)
		except ValueError as e:
			logger.critical("ERROR in json generation "+str(e))
		myFile.close()
		myFileinfo = os.stat(fout)
		logger.info("generate json file %s : %d bytes" % (fout, myFileinfo.st_size))
		logger.debug(data)
		return True

	def scandir(self, dirpath, dirs, files):
		nbdirs = len(dirs)
		nbfiles = len(files)
		scanid = '.'.join(map(str, self.scanid))

		info = {}
		info['folder'] = self.idx
		info['nbfiles'] = nbfiles
		info['url'] = 'url to add'

		# manage deep as
		# <li>
		#	<ul><li>
		#		<ul><li>
		info['deep'] = len(self.scanid)
		# deep previous element
		info['deepbefore'] = self.lenidbefore
		# deep need to close </li></ul> will be managed after everybody is filled
		# for moment, just say no
		logger.debug(info)
		self.toclist[scanid] = info
		#self.toclist[scanid] = ( self.idx, nbfiles, 'url to add' )
		logger.info("IDX %s %s%s" %(str(self.scanid), self.idx, " ("+str(nbfiles)+")" if nbfiles > 0 else ""))
		self.tochtml.append("%s %s%s" %(str(self.scanid), self.idx, " ("+str(nbfiles)+")" if nbfiles > 0 else ""))
		#return scanid

	def scanfile(self, tocid, scanfor, dirpath, filename, i):
		fname = os.path.join(dirpath,filename)
		if fname.endswith(scanfor):
			try:
				statinfo = os.stat(fname)
				logger.info(" file: "+fname+" size: "+str(statinfo.st_size))
				#info = self.toclist[tocid]
				#info = {'file':fname}
				#info['file'] = fname
				#info['filesize'] = statinfo.st_size

				# load markdown
				logger.info("load markdown file "+ fname)
				html = markdown2.markdown_path(fname, extras=["header-ids", "metadata", "toc"])
				if not html:
					logger.info("error in markdown file :"+fname)
					return False

				url = plw_get_url(fname)
				html.metadata['url'] = url[0]
				html.metadata['content'] = html
				html.metadata['scanfile'] = fname
				html.metadata['scanfilesize'] = statinfo.st_size

				self.toclist[tocid]['scan'][i] = {}
				self.toclist[tocid]['scan'][i] = html.metadata
			except ValueError as e:
				logger.critical("Error as "+str(e))
				return False
			return True
		else:
			return False



# MAIN
#
#
