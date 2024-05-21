// Interactive JS code for the CMA viewer/modeler

var MAP;
var images;


// Stuff to do when the page loads
function onLoad() {
    
    
   
    
    // Build map layer control
    createLayerControl();
    
}

function createLayerControl() {
    
    // Re-sort images list by group
    
    // TODO: populate these
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
                layers: [
                    L.vectorGrid.protobuf(
                        'https://dev.macrostrat.org/tiles/carto/{z}/{x}/{y}', {
                        attribution: 'Macrostrat'
                    }),
                ],
                legend: '',
            },
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
        wms_url0,
        legend,
        style_opts
    ) {
    opacity = opacity || 0.7;
    
//     console.log(wms_layer_name,wms_url0);
    
    wms_url0 = wms_url0 || WMS_URL;
    
    var data = {
        layers: wms_layer_name,
//         map: '/var/www/mapfiles/fra.map',
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
    
    if (wms_url0 == WMS_URL) {
        data.map = '/var/www/mapfiles/statmagic.map';
    }
    
    var layer = L.tileLayer.wms(wms_url0, data);
    
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
