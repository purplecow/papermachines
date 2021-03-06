#!/usr/bin/env python2.7
import sys, os, json, logging, traceback, base64, time, codecs
from collections import defaultdict
import cPickle as pickle
import geoparser

class GeoparserFlightPaths(geoparser.Geoparser):
	"""
	Visualize geoparser output as "flight paths"
	"""

	def _basic_params(self):
		self.name = "geoparser_flightpaths"
		self.dry_run = False
		self.require_stopwords = False
		self.template_filename = os.path.join(self.cwd, "templates", "geoparser_flightpaths.html")

	def process(self):
		"""
		create a JSON file with geographical data extracted from texts
		"""

		csv_input = os.path.join(self.out_dir, 'geoparser_export' + self.collection + '.csv')
		if not os.path.exists(csv_input):
			import geoparser_export
			subprocessor = geoparser_export.GeoparserExport()
			subprocessor.process()

		validEntityURIs = set()
		linksByYear = {}
		itemIDToYear = {}
		places = {}
		contexts = defaultdict(dict)

		try:
			for rowdict in self.parse_csv(csv_input):
				validEntityURIs.add(rowdict["entityURI"])
		except:
			logging.error(traceback.format_exc())
			sys.exit(1)

		if len(validEntityURIs) == 0: #empty csv file
			os.remove(csv_input)
			logging.error("Geoparser output file was empty!")
			sys.exit(1)

		for filename in self.files:
			file_geoparsed = filename.replace(".txt", "_geoparse.json")
			contexts_json = filename.replace(".txt", "_contexts.json")
			if os.path.exists(file_geoparsed):
				try:
					geoparse_obj = json.load(file(file_geoparsed))
				except:
					logging.error("File " + file_geoparsed + " could not be read.")
					continue
			else:
				continue
			if geoparse_obj.get('city') is None:
				continue
			try:
				title = os.path.basename(filename)
				itemID = self.metadata[filename]['itemID']
				if not self.metadata[filename]['year'].isdigit():
					continue
				year = int(self.metadata[filename]['year'])
				if year < 100:
					year += 1900
				elif year < 200:
					year += 1800

				itemIDToYear[itemID] = year

				if year not in linksByYear:
					linksByYear[year] = {}
				source = geoparse_obj.get('city')
				places[source] = geoparse_obj["places_by_entityURI"][source]
				for target in geoparse_obj.get('places'):
					if target in validEntityURIs:
						places[target] = geoparse_obj["places_by_entityURI"][target]
						edge = ','.join([source, target])
						if edge not in linksByYear[year]:
							linksByYear[year][edge] = {}
						if itemID not in linksByYear[year][edge]:
							linksByYear[year][edge][itemID] = 0
						linksByYear[year][edge][itemID] += 1
				if os.path.exists(contexts_json):
					with file(contexts_json) as f:
						contexts_obj = json.load(f)
				else:
					contexts_obj = self.contexts_from_geoparse_obj(geoparse_obj, filename)
				for geonameid, paragraphs in contexts_obj.iteritems():
					contexts[geonameid].update({itemID: paragraphs})
			except:
				logging.info(traceback.format_exc())

		years = sorted(linksByYear.keys())
		groupedLinksByYear = {}
		for year in years:
			groupedLinksByYear[year] = []
			for edge, text_weights in linksByYear[year].iteritems():
				weight = sum(text_weights.values())
				texts = text_weights.keys()
				source, target = edge.split(',')
				groupedLinksByYear[year].append({'edge': [source, target], 'texts': texts, 'year': year, 'weight': weight})

		# max_count = 0
		counts = {}
		for rowdict in self.parse_csv(csv_input):
			# coords = ','.join([rowdict["lat"], rowdict["lng"]])
			itemID = rowdict["itemID"]
			if itemID not in itemIDToYear:
				continue

			year = itemIDToYear[itemID]
			entityURI = rowdict["entityURI"]
			if "counts" not in places[entityURI]:
				places[entityURI]["counts"] = {}
			if year not in places[entityURI]["counts"]:
				places[entityURI]["counts"][year] = 0			
			places[entityURI]["counts"][year] += 1

		params = {"STARTDATE": min(linksByYear.keys()),
			"ENDDATE": max(linksByYear.keys()),
			"ENTITYURIS": places,
			"YEARS": years,
			"LINKS_BY_YEAR": groupedLinksByYear,
			"CONTEXTS": dict(contexts)
		}
		self.write_html(params)

		logging.info("finished")


if __name__ == "__main__":
	try:
		processor = GeoparserFlightPaths(track_progress=True)
		processor.process()
	except:
		logging.error(traceback.format_exc())