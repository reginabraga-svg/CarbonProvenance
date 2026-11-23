// CarboFarm soil carbon stock (0 to 30 cm, t C/ha) by municipality and land cover class in 2021.
// Exported source combinations:
//   Soil beta 2.1 and land cover 7.1 as used by CarboFarm.
//   Soil collection 3 and land cover 7.1 with the soil source revised.
//   Soil collection 3 and land cover 10 with both sources revised.
// Output: a CSV table in the EarthEngine folder on Google Drive.

// Locate an image in a MapBiomas asset folder.
function imagemNaPasta(pasta, preferido) {
  var itens = ee.data.listAssets(pasta).assets || [];
  var imgs = itens.filter(function (a) { return a.type === 'IMAGE'; });
  var pref = imgs.filter(function (a) { return a.id.indexOf(preferido) >= 0; });
  var escolhido = (pref.length ? pref : imgs)[0];
  print('Folder ' + pasta + ' -> selected ' + (escolhido ? escolhido.id : 'NOT FOUND') +
        '\n(items: ' + itens.map(function (a) { return a.id.split('/').pop(); }).join(', ') + ')');
  return ee.Image(escolhido.id);
}

// 1. Municipality boundaries from geoBoundaries, based on IBGE boundaries for Brazil.
var municipiosCarboFarm = [
  {cod: 1100908, nome: 'Castanheiras'}, {cod: 2312908, nome: 'Sobral'},
  {cod: 3142106, nome: 'Miradouro'}, {cod: 4319802, nome: 'São Vicente do Sul'},
  {cod: 5107602, nome: 'Rondonópolis'}, {cod: 5107768, nome: 'Santa Rita do Trivelato'}];
var nomes = municipiosCarboFarm.map(function (m) { return m.nome; });
var adm2 = ee.FeatureCollection('WM/geoLab/geoBoundaries/600/ADM2')
  .filter(ee.Filter.eq('shapeGroup', 'BRA'))
  .filter(ee.Filter.inList('shapeName', nomes));
var codPorNome = ee.Dictionary.fromLists(nomes, municipiosCarboFarm.map(function (m) { return m.cod; }));
var selecionados = adm2.map(function (f) { return f.set('cod', codPorNome.get(f.get('shapeName'))); });
print('1. Municipalities found (expected: 6):', selecionados.size());
print('   Names:', selecionados.aggregate_array('shapeName'));

// 2. Source images
var cobertura71 = imagemNaPasta('projects/mapbiomas-public/assets/brazil/lulc/collection7_1', 'integration')
  .select('classification_2021');
var cobertura10 = imagemNaPasta('projects/mapbiomas-public/assets/brazil/lulc/collection10', 'coverage')
  .select('classification_2021');
var soloBeta21 = ee.ImageCollection('projects/mapbiomas-workspace/SOLOS/PRODUTOS_BETA/soil_organic_carbon-0_30_cm_t_ha-beta_2_1')
  .select('prediction_2021').mosaic();     // Mosaic the 49 beta 2.1 tiles.
var soloCol3 = ee.Image('projects/mapbiomas-public/assets/brazil/soil/collection3/mapbiomas_brazil_collection3_soil_carbon_v1')
  .select('carbon_2021');
print('2. Bands: land cover 7.1', cobertura71.bandNames(), 'land cover 10', cobertura10.bandNames(),
      'soil beta 2.1', soloBeta21.bandNames(), 'soil collection 3', soloCol3.bandNames());

// 3. Mean by municipality and class with negative soil pixels excluded.
function medias(solo, cobertura, versaoSolo, versaoCobertura) {
  var valido = solo.gte(0);
  var img = solo.updateMask(valido).rename('soc')
    .addBands(cobertura.updateMask(valido).rename('classe'));   // Retain classes only where soil values are valid.
  var reducer = ee.Reducer.mean().combine(ee.Reducer.count(), '', true)
    .group({groupField: 1, groupName: 'classe'});
  return selecionados.map(function (f) {
    var r = img.reduceRegion({
      reducer: reducer, geometry: f.geometry(), scale: 30,
      crs: cobertura.projection(), maxPixels: 1e13, tileScale: 4
    });
    return ee.FeatureCollection(ee.List(r.get('groups')).map(function (g) {
      g = ee.Dictionary(g);
      return ee.Feature(null, {
        cod: f.get('cod'), municipio: f.get('shapeName'), versao_solo: versaoSolo,
        versao_cobertura: versaoCobertura, classe: g.get('classe'),
        media_t_C_ha: g.get('mean', null), pixels: g.get('count', null)
      });
    }));
  }).flatten();
}

var tabela = medias(soloBeta21, cobertura71, 'beta_2_1', 'col_7_1')
  .merge(medias(soloCol3, cobertura71, 'col_3', 'col_7_1'))
  .merge(medias(soloCol3, cobertura10, 'col_3', 'col_10'));

// 4. Export to Google Drive
Export.table.toDrive({
  collection: tabela,
  description: 'carbofarm_solo_2021_versoes',
  folder: 'EarthEngine',
  fileFormat: 'CSV',
  selectors: ['cod', 'municipio', 'versao_solo', 'versao_cobertura', 'classe', 'media_t_C_ha', 'pixels']
});
print('3. Open Tasks and select Run for carbofarm_solo_2021_versoes.');
