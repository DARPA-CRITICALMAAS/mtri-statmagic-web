// Interactive JS code for the CMA viewer/modeler
const WMS_URL = `https://apps2.mtri.org/mapserver/wms?`;
var images;


// Stuff to do when the page loads
function onLoad() {
    
    // Build map layer control
    createLayerControl();
    
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
        position: 'topright',
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

onLoad();
