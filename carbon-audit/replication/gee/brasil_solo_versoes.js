// Brazil soil carbon stock (0 to 30 cm, t C/ha) and area (ha) by municipality and land cover class.
// Years 2017 to 2021 under three source version combinations:
//   A: soil beta 2.1 and land cover 7.1.
//   B: soil collection 3 and land cover 7.1.
//   C: soil collection 3 and land cover 10.
// Create one CSV export task per combination in the EarthEngine folder on Google Drive.

var ANOS = [2017, 2018, 2019, 2020, 2021];

// Locate an image in a MapBiomas asset folder.
function imagemNaPasta(pasta, preferido) {
  var itens = ee.data.listAssets(pasta).assets || [];
  var imgs = itens.filter(function (a) { return a.type === 'IMAGE'; });
  var pref = imgs.filter(function (a) { return a.id.indexOf(preferido) >= 0; });
  var escolhido = (pref.length ? pref : imgs)[0];
  print('Folder ' + pasta + ' -> selected ' + (escolhido ? escolhido.id : 'NOT FOUND'));
  return ee.Image(escolhido.id);
}

// 1. Municipality and state boundaries. Assign the state containing the municipality centroid.
var adm2 = ee.FeatureCollection('WM/geoLab/geoBoundaries/600/ADM2').filter(ee.Filter.eq('shapeGroup', 'BRA'));
var adm1 = ee.FeatureCollection('WM/geoLab/geoBoundaries/600/ADM1').filter(ee.Filter.eq('shapeGroup', 'BRA'));
var centros = adm2.map(function (f) { return ee.Feature(f.geometry().centroid(100), {id: f.get('shapeID')}); });
var comUF = ee.Join.saveFirst('estado').apply(centros, adm1,
  ee.Filter.intersects({leftField: '.geo', rightField: '.geo', maxError: 100}));
var ufPorId = ee.Dictionary.fromLists(
  comUF.aggregate_array('id'),
  comUF.map(function (f) { return f.set('uf', ee.Feature(f.get('estado')).get('shapeName')); }).aggregate_array('uf'));
var municipios = adm2.map(function (f) {
  return f.set('uf', ufPorId.get(f.get('shapeID'), 'sem_uf'));
}).select(['shapeID', 'shapeName', 'uf']);
print('1. Municipalities (approximately 5,570 expected):', municipios.size());
print('   Example:', municipios.first());

// 2. Source images
var cob71 = imagemNaPasta('projects/mapbiomas-public/assets/brazil/lulc/collection7_1', 'integration');
var cob10 = imagemNaPasta('projects/mapbiomas-public/assets/brazil/lulc/collection10', 'coverage');
var soloBeta = ee.ImageCollection('projects/mapbiomas-workspace/SOLOS/PRODUTOS_BETA/soil_organic_carbon-0_30_cm_t_ha-beta_2_1').mosaic();
var soloCol3 = ee.Image('projects/mapbiomas-public/assets/brazil/soil/collection3/mapbiomas_brazil_collection3_soil_carbon_v1');
print('2. Soil beta 2.1 bands:', soloBeta.bandNames());
print('   Soil collection 3 bands:', soloCol3.bandNames());

// 3. Soil mean and area by municipality, class and year.
// Bands: 0 = soil carbon (t C/ha), 1 = pixel area (ha), 2 = class. Mean uses band 0 and sum uses band 1.
var redutor = ee.Reducer.mean().combine(ee.Reducer.sum(), '', false).group({groupField: 2, groupName: 'classe'});

function tabelaAno(solo, bandaSolo, cobertura, ano, versaoSolo, versaoCob) {
  var s = solo.select(bandaSolo);
  var valido = s.gte(0);
  var img = s.updateMask(valido).rename('soc')
    .addBands(ee.Image.pixelArea().divide(10000).updateMask(valido).rename('area_ha'))
    .addBands(cobertura.select('classification_' + ano).updateMask(valido).rename('classe'));
  var porMun = img.reduceRegions({
    collection: municipios, reducer: redutor, scale: 30, crs: cobertura.projection(), tileScale: 8
  });
  return porMun.map(function (f) {
    return ee.FeatureCollection(ee.List(f.get('groups')).map(function (g) {
      g = ee.Dictionary(g);
      return ee.Feature(null, {
        id: f.get('shapeID'), municipio: f.get('shapeName'), uf: f.get('uf'), ano: ano,
        versao_solo: versaoSolo, versao_cobertura: versaoCob, classe: g.get('classe'),
        media_t_C_ha: g.get('mean', null), area_ha: g.get('sum', null)
      });
    }));
  }).flatten();
}

function combinacao(solo, prefixoBanda, cobertura, versaoSolo, versaoCob) {
  var t = ee.FeatureCollection([]);
  ANOS.forEach(function (ano) {
    t = t.merge(tabelaAno(solo, prefixoBanda + ano, cobertura, ano, versaoSolo, versaoCob));
  });
  return t;
}

var COLUNAS = ['id', 'municipio', 'uf', 'ano', 'versao_solo', 'versao_cobertura', 'classe', 'media_t_C_ha', 'area_ha'];
[
  ['brasil_solo_A_beta21_cob71', soloBeta, 'prediction_', cob71, 'beta_2_1', 'col_7_1'],
  ['brasil_solo_B_col3_cob71', soloCol3, 'carbon_', cob71, 'col_3', 'col_7_1'],
  ['brasil_solo_C_col3_cob10', soloCol3, 'carbon_', cob10, 'col_3', 'col_10']
].forEach(function (c) {
  Export.table.toDrive({
    collection: combinacao(c[1], c[2], c[3], c[4], c[5]),
    description: c[0], folder: 'EarthEngine', fileFormat: 'CSV', selectors: COLUNAS
  });
});
print('3. Open Tasks and select Run for the three exports (brasil_solo_A, B and C).');
