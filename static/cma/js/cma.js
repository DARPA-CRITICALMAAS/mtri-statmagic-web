// Interactive JS code for the CMA viewer/modeler
const WMS_URL = `https://apps2.mtri.org/mapserver/wms?`;
const MAPFILE = '/var/www/mapfiles/statmagic.map';
var images;
var drawnItems = new L.FeatureGroup();
var drawnLayer;
var AJAX_GET_MINERAL_SITES;


// Stuff to do when the page loads
function onLoad() {
    
    // Creates map layers from the datalayers lookup
    createMapLayers();
    
    // Build map layer control
    createLayerControl();
    
    // Add draw control to map 
    addDrawControl();
    
    // Add mineral sites contrl
//     createMineralSitesControl();
    
    // Toggle open the DATA LAYERS panel by default
    toggleHeader($('#datalayer_container .header.toptop'));
    toggleHeader($('#datalayer_container .header.Geophysics'));
}

// function buildDataLayer

function createMapLayers() {
    
    $.each(DATALAYERS_LOOKUP, function(name,obj) {
        obj.maplayer = L.tileLayer.wms(
            WMS_URL, {
                layers: name,
                map: MAPFILE,
                format: 'image/png',
                crs: L.CRS.EPSG4269,
                transparent: true,
                width: 512,
                height: 512,
                opacity: 0.8,
                maxZoom: 30,
                zIndex: 200,
//                     data_id: wms_layer_name
        
        });
    });
    
}

function createLayerControl() {
    
    // Create a popup to use in the macrostrat layer
    var popup = L.popup({
        minWidth: 260,
        autoPan: false,
    });
            
    macrostrat_layer = L.vectorGrid.protobuf(
        'https://dev.macrostrat.org/tiles/carto/{z}/{x}/{y}', {
        attribution: 'Macrostrat',
        interactive: true,
        vectorTileLayerStyles: {
            units: {
                weight: 0.5,
                color: '#c96303',
                fillColor: '#fdc086',
                fillOpacity: 0.2,
                fill: true,
            },
            lines: {
                weight: 2,
                color: '#7fc97f',
            }
        },
    }),
    macrostrat_layer.bindPopup(popup);
    macrostrat_layer.on('click', function(e) {
        popup.setContent(`<h2>${e.layer.properties.name}</h2>`);
        macrostrat_layer.openPopup();
    });
    macrostrat_layer.on('mouseover', function(e) {
        console.log(e.layer);
//         e.layer.setStyle({weight: 1});//, fillOpacity: 0.7});

        
    });
//     macrostrat_layer.on('mouseout', function(e) {
// //         console.log(e.layer);
// //         alert(e.layer.properties.name);
//         e.layer.setStyle({weight: 0.5});//, fillOpacity: 0.2});
//         
//     });
    
    
    // Populate the 'images2' object
    // key: the layer control group (e.g. 'imagery','other','features', etc.)
    // values: object with:
    //      key: WMS layername
    //      value: object returned from "getWMSLayer"
    var images2 = {
        'Layers': {
            'macrostrat': {
                group: 'Layers',
                label: 'Macrostrat',
                as_checkbox: true,
                title: '',
                layers: [macrostrat_layer],
                legend: '',
            },
            'geophysics': getWMSLayer(
                'geophysics',
                'Layers',
                'GeophysicsMagRTP',
                null,
                ''
            ),
        },
    };
    images2 = {}
    var groups = Object.keys(images2).sort();
    images = {};
    var i = 0;
    $.each(groups, function(g,group) {
        $.each(Object.keys(images2[group]).sort(), function(ik,ikey) {
            i += 1;
            var key_new = `${String(i).padStart(3,'0')}_${ikey}`;
            images[key_new] = images2[group][ikey];
        });
    });

    clc = new CustomLayerControl(images, basemap_options, groups, {
        collapsed: false,
        position: 'bottomright',
        organize_imagery: true
    });

    clc.addTo(MAP);
    
    // Add toggle function to header rows
    $('.header:not(.m-basemap-selector)').unbind('click');
    $('.header:not(.m-basemap-selector)').click(function(){
        toggleHeader(this);
    });
    $('.m-basemap-selector.header').click(function(){
        toggleLayerHeader(this);
    });
    
    // Hide legends
    $('.other-legend').hide();
}

function getWMSLayer(
        wms_layer_name,
        group,
        label,
        opacity,
        legend,
        style_opts
    ) {
    opacity = opacity || 0.7;
    
    var data = {
        layers: wms_layer_name,
        map: '/var/www/mapfiles/statmagic.map',
        format: 'image/png',
        crs: L.CRS.EPSG4269,
        transparent: true,
        width: 512,
        height: 512,
        opacity: opacity,
        maxZoom: 30,
        zIndex: 200,
        data_id: wms_layer_name
    }
    
    var layer = L.tileLayer.wms(WMS_URL, data);
    
    return {
        group: group,
        label: label,
        as_checkbox: true,
        title: '',
        layers: [layer],
        legend: legend,
    };
}

// function getWMSLayer(wms_layer_name,group,label,opacity) {
//     opacity = opacity || 0.7;
//     return {
//         group: group,
//         label: label,
//         title: '',
//         layers: [
//            L.tileLayer.wms(
//                 WMS_URL, {
//                     layers: wms_layer_name,
//                     map: MAPFILE,
//                     format: 'image/png',
//                     crs: L.CRS.EPSG4269,
//                     transparent: true,
//                     width: 512,
//                     height: 512,
//                     opacity: opacity,
//                     maxZoom: 30,
//                     zIndex: 200,
//                     data_id: wms_layer_name
//                 }
//             )
//         ],
//         legend: ``
//     };
// 
// }

function addDrawControl() {
    // Add draw control and functionality
    var draw_style = {
        color: 'orange',
        weight: 4,
        opacity: 1,
        fillOpacity: 0.1,
        strokeOpacity: 1,
        pointerEvents: 'None'
    }
    
    var drawControl = new L.Control.Draw({
        draw: {
            polyline: false,
            polygon: {
                shapeOptions: draw_style
            },
            circle: false,
//             marker: {
//                 icon: marker_icon
//             },
            rectangle: {
                shapeOptions: draw_style
            },
            circlemarker: false,
            marker: false,
        },
        edit: {
            featureGroup: drawnItems,
            edit: false
        },
        position: 'bottomleft',
    });
    
    // Add layer to the map that holds drawn items
    MAP.addLayer(drawnItems);

    // Add draw control tools to map
    MAP.addControl(drawControl);
    
    // Draw event handlers
    MAP.on(L.Draw.Event.DRAWSTART, function(e) {
        // Remove existing drawings before starting new one
        if (drawnLayer && MAP.hasLayer(drawnLayer)) {
            MAP.removeLayer(drawnLayer);
        }
    });
    
    MAP.on(L.Draw.Event.CREATED, function(e) {
        drawnLayer = e.layer;
        drawnItems.addLayer(drawnLayer);
        finishDraw(drawnLayer);
    });
    MAP.on(L.Draw.Event.EDITED, function(e) {
        var layer = e.layers.getLayers()[0];
        finishDraw(layer);
    });
    
    MAP.on(L.Draw.Event.DELETED, function(e) {
        console.log('deleted!');
        drawnLayer = null;
        validateLoadSitesButton();
    });
}

function finishDraw(layer) {
    // Zoom to drawn polygon
    MAP.fitBounds(layer.getBounds(),{padding: [80,80]});
    
    // Enable/disable load sites button
    validateLoadSitesButton();
}

function loadMineralSites() {
    // Request the selected sites
    
    // First abort any requests to the same endpoint that are in progress
    if (AJAX_GET_MINERAL_SITES) {
        AJAX_GET_MINERAL_SITES.abort();
    }
    AJAX_GET_MINERAL_SITES = $.ajax(`/get_mineral_sites`, {
        data: {
            commodity: $('#commodity').val(),
            wkt: getWKT()
        },
        success: function(response) {
        },
        error: function(response) {
            console.log(response);
        }
    });
    
}

function createMineralSitesControl() {
    
    // Create "Load Mineral Sites" control
    
    // Create html *select* options list of commodities
    var opts_html = '<option value="" disabled selected hidden>Select...</option>';
    $.each(COMMODITIES, function(i, name) {
        opts_html += `<option value="${name}">${name}</option>`;
    });
    
    var controlPanel = L.Control.extend({
        options: {
            position: 'topleft'
        },

        onAdd: function () {
            var c = L.DomUtil.create('div', 'controlPanel');
            
            c.innerHTML = `
                <table>
                    <tr class='title'>
                        <td colspan=2>Load mineral sites</td>
                    </tr>
                    <tr>
                        <td class='label'>Commodity:</td>
                        <td>
                            <select id='commodity' onChange="validateLoadSitesButton();">
                                ${opts_html}
                            </select>
                        </td>
                    </tr>
                    <tr>
                        <td class='label'>AOI:</td>
                        <td><div id='query_instructions'><span class="highlight">
                            (draw) poly <a onClick=drawStart("polygon")>
                            <img src="/static/cma/img/draw-polygon-icon.png" 
                                 height="17"
                                 id="draw_polygon_icon" /></a> | 
                            rect <a onClick=drawStart("rectangle")>
                            <img src="/static/cma/img/draw-rectangle-icon.png"
                                 height="17"
                                 id="draw_rectangle_icon" ></a>
                        </div></td>
                    </tr>
                    <tr>
                        <td colspan=2>
                            <div id="load_sites_button" class='button load_sites disabled' onClick='loadMineralSites();'>Load sites</div>
                        </td>
                    </tr>
                </table>
            `;

            return c;
        }
    });
    MAP.addControl(new controlPanel());
}

function validateLoadSitesButton() {
    var v = $('#commodity').val();
    if (v && drawnLayer) {
        $('#load_sites_button').removeClass('disabled');
    } else {
        $('#load_sites_button').addClass('disabled');
    }
}

function drawStart(layerType) {
    $('.leaflet-draw-draw-' + layerType)[0].click();
}

function getWKT() {
    
    // Convert the drawn layer to WKT so that it can be sent as a URL parameter
    var gj = drawnLayer.toGeoJSON();
    var new_coords = gj.geometry.coordinates[0].map(function(val) {
        return val.map(x => Number(x.toFixed(6)));
    });

    gj.geometry.coordinates = [new_coords];
    var wkt = new Wkt.Wkt();
    wkt.read(JSON.stringify(gj));
    
    // replace spaces w/ + bc can't put spaces in URL
    return wkt.write().replace(/ /g,'+'); 
    
}

function onToggleLayerClick(target,layer_name) {
    var chk = $(target);
    
    
    
//     // ID the associated checkbox
//     if (target.prop('nodeName') == 'INPUT') {
//         chk = $(target);
//     } else if (['SPAN','DIV','TD','TR'].indexOf(target.prop('nodeName')) > -1) {
//         chk = $(target.find('input')[0]);//$('#' + id + '-checkbox');
//         is_label = true;
//     }
//     
//     // Handle a click on the label 
//     if (chk.prop('type') == 'radio') {
//         if (is_label) {
//             chk.prop('checked',true);
//         }
//     } else {
//         if (is_label && !chk.prop('checked')) {
//             chk.prop('checked', true);
//         } else if (is_label && chk.prop('checked')) {
//             chk.prop('checked', false);
//         }
//     }
    
    var datalayer =  DATALAYERS_LOOKUP[layer_name];
    var layer = datalayer.maplayer;//bm ? map_obj.basemaps[layer_id] : CROSSINGS[crossing_id].layers[layer_id].layers[0];
    
    // Remove all layers in group
    if (chk.prop('checked')) {
        MAP.addLayer(layer);
        
        // Add color halo
        chk.css({
            'accent-color': `rgb(${datalayer.color})`
        });
    } else {
        MAP.removeLayer(layer);
    }
}

onLoad();
