// Check annual mean soil carbon stock (t C/ha) in Brazil across two soil source versions.
// Print results to the console without an export task.
var brasil = ee.FeatureCollection('WM/geoLab/geoBoundaries/600/ADM0').filter(ee.Filter.eq('shapeGroup', 'BRA')).geometry();
var col3 = ee.Image('projects/mapbiomas-public/assets/brazil/soil/collection3/mapbiomas_brazil_collection3_soil_carbon_v1');
var beta = ee.ImageCollection('projects/mapbiomas-workspace/SOLOS/PRODUTOS_BETA/soil_organic_carbon-0_30_cm_t_ha-beta_2_1').mosaic();
print('Collection 3 bands:', col3.bandNames());

function media(img, banda) {
  var b = img.select(banda);
  return b.updateMask(b.gte(0)).reduceRegion({reducer: ee.Reducer.mean(), geometry: brasil, scale: 1000, maxPixels: 1e13, bestEffort: true}).get(banda);
}
[2017, 2018, 2019, 2020, 2021, 2022].forEach(function (ano) {
  print('Year ' + ano, 'col. 3:', media(col3, 'carbon_' + ano), 'beta 2.1:', ano <= 2021 ? media(beta, 'prediction_' + ano) : '—');
});
