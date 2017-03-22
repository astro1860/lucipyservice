
import numpy as np
import json
import shapely
from shapely.geometry import Polygon
from sklearn import cluster,metrics
from scipy.spatial import distance
from descartes import PolygonPatch
import pdb


def luciobj(geomids, data):
# with open('/Users/chairia/Polybox/03_Projects/201701_quakit/data/geometry/3.json') as f:
# 	data = json.load(f)

	centroid_alles = []
	polygon_alles = []
	points_alles = []
	geomID = []
	for i,feature in enumerate(data['features']):
		if 'static' in feature['properties']:
			ifdynamic = False
		else:
			ifdynamic = True
		if (feature['geometry']["type"]=="MultiPolygon" or feature['geometry']["type"]=="Polygon") and ifdynamic:
			convexs = set()
			centroid = []
			geomID.append(feature['properties']['geomID'])
			for surfaces in feature['geometry']['coordinates']:
				surface = surfaces[0]
				surface_z = set(x[2] for x in surface)
				if len(surface_z) == 1:
					surface_2d = list((x[0],x[1]) for x in surface)
				for p in surface:
					convexs.add(tuple(p))

			# idgeo = feature['properties']['geomID']
			# geomID.append(idgeo)
			polygon = Polygon(surface_2d)
			polygon = shapely.geometry.polygon.orient(polygon)
			polygon_alles.append(polygon)

			#geomID.append(feature['properties']['geomID'])


	adj_poly = np.zeros((len(polygon_alles),len(polygon_alles)))
	for c,c_poly in enumerate(polygon_alles):
		for a,a_poly in enumerate(polygon_alles):
			adj_poly[c,a] = c_poly.distance(a_poly)

	pw_dis = list(adj_poly[np.triu_indices(len(polygon_alles))])
	pw = [y for y in pw_dis if y != 0.0]

	min_per = 2
	max_per = 5
	percentile = list(np.arange(min_per,max_per,0.1))
	min_samples_ = [3,4]
	eps_ = []
	para_dist = []

	si_max = -1

	for min_samples in min_samples_:
		for val in percentile:
			eps = np.percentile(pw,val)
			dbscan = cluster.DBSCAN(
				eps=eps,
				min_samples=min_samples,
				metric='precomputed')
			labels = dbscan.fit_predict(adj_poly)
			if(len(set(labels)) == 1):
				SI_score = 'NA'
			else:
				SI_score = metrics.silhouette_score(adj_poly,labels,metric="precomputed")
		   
				para_dist.append({'eps':eps,'min_sample':min_samples,'SI':SI_score})
				if (SI_score > si_max):
					si_max = SI_score
					para_set_max = [val,eps,min_samples]

	newlist = sorted(para_dist, key=lambda k: k['SI'],reverse=True) 
	good_para = newlist[0:1]

	for ind,val in enumerate(good_para):
	   
		eps = val['eps']
		min_samples = val['min_sample']
		SI_score = val['SI']
		dbscan = cluster.DBSCAN(eps=eps,min_samples=min_samples,metric='precomputed')
		labels = dbscan.fit_predict(adj_poly)
		#geo_val_list = []
		geoidval = {}
		for zipp in zip(geomID,list(labels)):
			#print(zipp[0],zipp[1])
			# geo_val = {}
			# geo_val['geomID'] = zipp[0]
			# geo_val['value'] = zipp[1]
			# geo_val_list.append(geo_val)
			geoidval[str(zipp[0])] = zipp[1]

		values = []
		for geomid in geomids:
			if geomid in set(geomID):
				values.append(geoidval[str(geomid)])

		#print(geo_val_list)

	return values,geoidval








