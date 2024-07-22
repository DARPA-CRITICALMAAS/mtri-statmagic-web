// Interactive JS code for the CMA viewer/modeler
// const WMS_URL = `http://${MAPSERVER_SERVER}.mtri.org/cgi-bin/mapserv?`;
const WMS_URL = `https://apps2.mtri.org/mapserver/wms?`;
const MAPFILE = '/var/www/mapfiles/statmagic.map';
var COMMODITIES;
const REQUIRED_SHP_EXTS = ['shp','shx','prj','dbf'];
var images;
var drawnItems = new L.FeatureGroup();
var drawnLayer;
var DATACUBE_CONFIG = [];
var FISHNET_LAYER = new L.FeatureGroup();
const DRAW_STYLE = {
    color: 'orange',
    weight: 4,
    opacity: 1,
    fillOpacity: 0.01,
    strokeOpacity: 1,
    pointerEvents: 'None'
}
var AJAX_GET_MINERAL_SITES, AJAX_UPLOAD_SHAPEFILE, AJAX_GET_FISHNET;


// Stuff to do when the page loads
function onLoad() {
    
    // Creates map layers from the datalayers lookup
    createMapLayers();
    
    // Add fishnet layer
    MAP.addLayer(FISHNET_LAYER);
    
    // Build map layer control
    createLayerControl();
    
    // Add loading spinner control
    addLoadingSpinnerControl();
    
    // Add top CMA choose control
    addCMAControl();
    
    // Load CRS options
    var opts = ``;
    $.each(CRS_OPTIONS, function(crs,cobj) {
        var selected = crs == 'Conus Albers (EPSG:5070)' ? ' selected' : '';
        opts += `<option value='${crs}'${selected}>${crs}</option>`;
    });
    $('#cma_crs').html(opts);
    
    // Add listeners for CMA initiate parameter validation
    $('#cma_initialize_params input').on('change', function(el) {
        validateCMAinitializeForm(el);
    });

    $('#cma_mineral').on('input', function(e) {
        var mineral = $(e.target).val();
        var date = getDateAsYYYYMMDD();
        var desc = $('#cma_description').val();
        if (desc == '' || desc == `${mineral.slice(0,mineral.length-1)}_${date}`) {
            $('#cma_description').val(`${mineral}_${date}`);
        }
    });
    
    // Add draw control to map 
    addDrawControl();
    
    // Trigger CRS select to load units/resolution  
    onCRSselect();
    
    // Populate ProcessinStep options
    populateAddProcessingStep();
    
    // Create legend control
    createLegendControl();
    
    // Have the leaflet map update it's size after the control_panel show/hide
    // transition completes
    $('.flex-child.control_panel').on('transitionend webkitTransitionEnd oTransitionEnd', function() {
        MAP.invalidateSize();
    });
    
    // Add control panel collapse listener
    $('#sidebar_collapse_button').on('click',function(e) {
        var cmp = $(e.target);
        var closed = cmp.html() == '⯈';

        if (closed) {
            $('.flex-child.control_panel').css('width','40%');
            $('.collapse.modeling').show(); // see below vvv
            cmp.html('⯇');
        } else {
            $('.flex-child.control_panel').css('width','0');
            $('.collapse.modeling').hide(); // <- hack b/c contents squeeze out bottom otherwise
            cmp.html('⯈');
        } 

    });
    
    // Set default CRS to CONUS Albers
    $('#cma_crs').val("Conus Albers (EPSG:5070)");
    onCRSselect();
    
    // Load models to dropdown
    var opts = `<option disabled value='' selected hidden>Select...</option>`;
    $.each(MODELS, function(i,m) {
        opts += `<option value='${m.name}'>${m.name_pretty}</option>`;
    });
    $('#model_select').html(opts);
    
    // Add mineral sites contrl
//     createMineralSitesControl();
    
    // Toggle open the DATA LAYERS panel by default
    toggleHeader($('#datalayer_container .header.toptop'));
    toggleHeader($('#datalayer_container .header.Geophysics'));
    
    toggleHeader($('.header.modeling'));
    toggleHeader($('.header.datacube'));
    
    // Get metadata
    getMetadata();
}

function addCMAControl() {
    var Title = L.Control.extend({
        options: {
            position: 'topright'
        },

        onAdd: function () {
            var c = L.DomUtil.create('div', 'cma_header');
            
            c.innerHTML = `
                <div class='cma_start_div'>
                    <table>
                        <tr>
                            <td>
                                <div id="btn_cma_initialize" class='button load_sites cma' onClick='showInitializeCMAform();'>Initiate CMA</div>
                            </td>
                            <td>
                                <div id="btn_cma_load" class='button load_sites cma' onClick='loadCMA();'>Load CMA</div>
                            </td>
                        </tr>
                        <tr>
                            <td colspan=2>CMA: <span id='cma_loaded' class='notactive'>[none active]</span></td>
                        </tr>
                    </table>
                </div>
                
                <div id="cma_initialize_form">
                    <div class='cma_navigate' onclick='showCMAstart();'>&#11178</div>
                    <div class='cma_initiate_title'>Initiate CMA</div>
                    <table id='cma_initialize_params' class='modeling_params'>
                        <tr>
                            <td class='label'>CMA mineral:</td>
                            <td><input type='text' id='cma_mineral' /></td>
                        </tr>
                        <tr>
                            <td class='label'>CMA description:</td>
                            <td><input type='text' id='cma_description' /></td>
                        </tr>
                        <tr>
                            <td class='label'>CRS:</td>
                            <td>
                                <select id='cma_crs' onChange='onCRSselect();'>
                                </select>
                            </td>
                        </tr>
                        <tr>
                            <td class='label'>Spatial res. (<span id='cma_crs_units'></span>):</td>
                            <td><input type='number' id='cma_resolution' /></td>
                        </tr>
                        <tr>
                            <td class='label'>Extent:</td>
                            <td>
                                <span class='link' onclick="$('#file_geojson').trigger('click')";">geojson</span> / <span class='link' onclick="$('.modal_uploadshp').show();">shp</span> / draw: <a onClick=drawStart("polygon")>
                                <img src="/static/cma/img/draw-polygon-icon.png" 
                                    height="17"
                                    id="draw_polygon_icon" /></a>
                                <a onClick=drawStart("rectangle")>
                                <img src="/static/cma/img/draw-rectangle-icon.png"
                                    height="17"
                                    id="draw_rectangle_icon" ></a>
                            </td>
                        </tr>
                    </table>
                    <div class='cma_button_container'>
                        
                        <div id="btn_cma_initialize_cancel" class='button load_sites cmainit cancel' onClick='showCMAstart();'>Cancel</div>
                        <div id="btn_cma_initialize_submit" class='button load_sites cmainit' onClick='initiateCMA();'>Submit</div>
                    </div>
                    <div id='cma_validate_message' class='form_validation_message'></div>
                    <div id='cma_fishnet_message' class='form_validation_message'></div>
                </div> <!--cma_start_div-->
            </div> <!--cma_initialize_form-->
            `;

            return c;
        }
    });
    var c = new Title();
    c.addTo(MAP);
    
    // This is a hack to prevent tiles getting messed up on Safari-like browsers when CMA form is opened.
    MAP.setZoom(MAP.getZoom()+1);
    MAP.setZoom(MAP.getZoom()-1)
    
    // Add listeners to stop click propagation to underlying map 
    $('.cma_header input').on('dblclick', function(e) {
        console.log('stopping propagation');
        e.stopPropagation();
    });
    // This is for Safari browsers that for whatever reason pass the click 
    // through to the map instead of focusing on the input element
    $('.cma_header input').on('click', function(e) {
        $(e.target).focus();
    });
    
}

function addLoadingSpinnerControl() {
    var Title = L.Control.extend({
        options: {
            position: 'bottomright'
        },

        onAdd: function () {
            var c = L.DomUtil.create('div', 'loading_fishnet');
            
            c.innerHTML = `...loading grid preview <div class='loading_spinner'></div>`;

            return c;
        }
    });
    var c = new Title();
    c.addTo(MAP);
}

function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

function buildParametersTable(obj, table_selector,dobj) {
    var showhide_groups = {};
    ptable_html = '<table class="model_parameters_table">';
    var group_current;
    $.each(Object.keys(obj.parameters).sort(), function(g,group_name) {
        if (group_name != '_') {
            ptable_html += `
                <tr class='subcategory_label'>
                    <td>${capitalizeFirstLetter(group_name)}</td>
                    <td></td>
                </tr>
            `;
        }
        $.each(obj.parameters[group_name], function(i,p) {
            var pid = `${obj.name}__${p.name}`;
            if (p.only_show_with) {
                var pshow = `${obj.name}__${p.only_show_with}`;
                if (!showhide_groups[pshow]) {
                    showhide_groups[pshow] = [];
                }
                showhide_groups[pshow].push(pid);
            }
            var input_html;
            if (p.input_type != 'select') {
                var attrs = '';
                var onChange = '';
    //             var onChange = p.input_type == 'checkbox' ? ' onchange="onModelParameterCheckboxChange(this);"' : '';
                
                if (p.html_attributes) {
                    $.each(p.html_attributes, function(attr,v) {
                        
                        // If default has been modified, use that value
                        if (attr == 'value' && dobj && dobj[p.name]) {
                            v = dobj[p.name];
                        }
    
                        attrs += ` ${attr}="${v}"`;
                    });
                }
                input_html = `
                    <input id="${pid}" type="${p.input_type}" ${attrs}${onChange} />
                `
            } else {
                var opts = '';
                if (p.options) {
                    $.each(p.options, function(j,opt) {
                        var selected = '';
                        
                        // If default has been modified, use that value
                        if (dobj && opt == dobj[p.name]) {
                            selected = ' selected';
                        }
                        opts += `<option value="${opt}"${selected}>${opt}</option>`;
                    });
                }
                input_html = `
                    <select id="${obj.name}__${p.name}">
                        ${opts}
                    </select>
                `;
            }
            
            ptable_html += `
                <tr id="${pid}_tr" title="${p.description}">
                    <td class='label'>${p.name_pretty}:</td>
                    <td>${input_html}</td>
                </tr>
            `;
            
        }); // parameter loop
    }); // group loop
    ptable_html += '</table>';
    
    $(table_selector).html(ptable_html);
    
    // Create listeners for show/hide checkboxes
    $.each(showhide_groups, function(chk,ps) {
        $(`#${chk}`).on('change', function(e) {
            var checked = $(e.target).is(':checked');
            $.each(ps, function(i,p) {
                $(`#${p}_tr`).toggle(checked);
            });
        });
    });
}

function onModelSelect() {
    var model = MODELS[$('#model_select').val()];
    
    // First hide everything
    $('.collapse_datacube').hide();
//     $('.collapse_parameters').hide();
//     $('.collapse_training').hide();
//     $('.collapse_model_run').hide();

    
    
    
    // Then build everything back up
    $('.selected_model_description').html(model.description);
    
    // Show CONFIG button
    $('.button.selected_model_config').show();
    
    // Show data cube builder interface
    if (model.uses_datacube) {
        $('.collapse_datacube').show();
    }
    
    // Show selection buttons in Data Layers
    $('.radiocube').show();
    
    // Build parameters table 
    buildParametersTable(model,'.content.model');
    
    

    // Now trigger change to set initial display
    
    
    // Build buttons
    var button_html = '';
    $.each(model.buttons.buttons, function(i,button) {
        console.log(i,button);
        button_html += `
            <td>
                <div class='button ${button.label}'>${button.label}</div>
            </td>`;
    });
    $('#modeling_buttons_table tr').html(button_html);
    
    
    // Show all sections
    $('.collapse_parameters').show();
    $('.collapse_training').show();
    $('.collapse_model_run').show();
    
    
  
    
    
    
}

function onModelParameterCheckboxChange(cmp) {
    console.log(cmp);
}

function getMetadata() {
    $.ajax(`/get_metadata`, {
        data: {},
        success: function(response) {
            COMMODITIES = response.commodities;
            
            // Now load these to the dropdown
            var opts = `<option disabled selected hidden>Select...</option>`;
            $.each(COMMODITIES, function(i,c) {
                opts += `<option value='${c}'>${c}</option>`;
            });
            $('#commodity').html(opts);
        },
        error: function(response) {
            console.log(response);
        }
    });
    
}

function getSelectedProcessingSteps() {
    var l = [];
    $('#processingsteps_listtable tr').each(function(i,cmp) {
        l.push($(cmp).attr('data-value'));
    });
    
    return l;
}

function populateAddProcessingStep() {
    // Get currently listed options
    var listed_steps = getSelectedProcessingSteps();
    
    var opts = `<option disabled selected hidden>Select...</option>`;
    $.each(PROCESSING_STEPS, function(p,obj) {
        if (listed_steps.indexOf(p) > -1) {
            return;
        }
        opts += `<option value='${p}'>${obj.name_pretty}</option>`;
    });
    $('#processingsteps_addstep').html(opts);

    
}

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
    
    var drawControl = new L.Control.Draw({
        draw: {
            polyline: false,
            polygon: {
                shapeOptions: DRAW_STYLE
            },
            circle: false,
//             marker: {
//                 icon: marker_icon
//             },
            rectangle: {
                shapeOptions: DRAW_STYLE
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
        
        // Clear fishnet
        FISHNET_LAYER.clearLayers();
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
    
    // TODO: If this drawing is for mineral sites:
    
    // Enable/disable load sites button
    validateLoadSitesButton();
    
    // TODO: If this drawing comes from CMA:
    getFishnet();
    
    // Validate CMA initialization form
    validateCMAinitializeForm();
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

function createLegendControl() {
    
    // Create legend control

    var legendControl = L.Control.extend({
        options: {
            position: 'topleft'
        },
        onAdd: function () {
            var c = L.DomUtil.create('div', 'legend');
            
            c.innerHTML = `<div id='legend_content'></div>`;

            return c;
        }
    });
    MAP.addControl(new legendControl());
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
    
    // A loaded-from-file GeoJSON layer may be a FeatureCollection, in which 
    // case we need to unwrap to find the first feature
    var gj = gj.geometry ? gj : gj.features[0];
    
    var new_coords = gj.geometry.coordinates[0].map(function(val) {
        return val.map(x => Number(x.toFixed(6)));
    });

    gj.geometry.coordinates = [new_coords];
    var wkt = new Wkt.Wkt();
    wkt.read(JSON.stringify(gj));
    
    // replace spaces w/ + bc can't put spaces in URL
    return wkt.write().replace(/ /g,'+'); 
    
}

function showDataLayerInfo(layer_name) {
    var dl = DATALAYERS_LOOKUP[layer_name];
    
    $('#dl_title').html(dl.name_pretty);
    $('#dl_description').html(`<span class='label'>Description:</span><br>${dl.description}`);
    $('#dl_url').html(`<span class='label'>Download URL:</span><br><a href='${dl.path}' target='_blank'>${dl.path}</a>`);
    $('#dl_source').html(`<span class='label'>Source:</span><br>${dl.source}`);
    
    $('#datalayer_info').show();
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
        
        // Add layer color to checkbox
        chk.css({
            'accent-color': `rgb(${datalayer.color})`
        });
        
        // Add legend content
        var w = 60;
        var h = 14;
        var lmin = datalayer.stats_minimum;
        var lmax = datalayer.stats_maximum;
        var precision = 3;//Math.max(-Math.round(Math.log10(lmax-lmin)),1);
        
        html = `
            <div class='layer_legend' id='legendcontent_${layer_name}'>
                ${datalayer.name_pretty}
                <table>
                    <tr>
                        <td>${lmin.toPrecision(precision)}</td>
                        <td>
                            <div class='colorbar'>
                                <svg height='${h}' width='${w}'>
                                    <linearGradient id="gradient_${layer_name}">
                                        <stop stop-color="#fff" offset="0%" />
                                        <stop stop-color="rgb(${datalayer.color})" offset="100%" />
                                    </linearGradient>
                                    <rect width="${w}" height="${h}" fill="url(#gradient_${layer_name})" />
                                </svg>
                            </div>
                        </td>
                        <td>${lmax.toPrecision(precision)}</td>
                    </tr>
                </table>
            </div>
        `;
        
        $('#legend_content').append(html);
        
        // Show legend
//         $('.legend.leaflet-control').show();
        
    } else {
        // Remove layer from map
        MAP.removeLayer(layer);

        // Remove legend content
        $(`#legendcontent_${layer_name}`).remove();
    }
}

function onRadioCubeClick(cmp) {
    var el = $(cmp);
    var for_radio = el.prop('for');
    var radio = $(`input[name='${for_radio}']`);
    var valnew = el.prop('class');
//     console.log(valnew);
    var layername = for_radio.replace('radiocube_','');
    
    // Update 'checked' property
    radio.prop('checked',false);
    $(`input[name='${for_radio}'][value='${valnew}']`).prop('checked',true);
    
    // Add/remove layer from the datacube layer list
    
    // Remove layer from cube
    if (valnew == 'no') {
        // TODO: if/when multiple instances of single data layer are allowed, 
        // this will need to be updated b/c data-layername might not be unique
        var dcid = $(`#datacube_layers tr[data-layername='${layername}']`).attr('data-datacubeindex');
        DATACUBE_CONFIG.splice(dcid,1);
        $(`#datacube_layers tr[data-layername='${layername}']`).remove();
        
        // If there are no rows left, show instructions again
        if ($('#datacube_layers tbody tr').length == 1) {
            $('#datacube_layers tr.instructions').show();
        }
    } else { // Add layer to cube
        var datalayer = DATALAYERS_LOOKUP[layername];
        DATACUBE_CONFIG.push({layername: layername, processingsteps: []});
        
        // Hide instructions 
        $('#datacube_layers tr.instructions').hide();
        
        // Add row 
        var icon_height = 13;
        $('#datacube_layers tr.cube_layer:last').after(`
            <tr class='cube_layer' data-layername='${layername}' data-datacubeindex=${DATACUBE_CONFIG.length-1}>
                <td class='name'>${datalayer.name_pretty}</td>
                <td class='processing'><span class='link processingsteps_list' onclick='editProcessingSteps(this);'>[none]</span></td>
                <td class='remove'>
                    <div class='img_hover' onclick=''>
                        <div class='snapshot' onclick="onRemoveDataCubeLayerClick(this);" title="Remove data layer from cube">
                            <img src="/static/cma/img/icon_trash2.png" height="${icon_height}px" />
                        </div>
                        <div class='snapshot' onclick="onRemoveDataCubeLayerClick(this);" title="Remove data layer from cube">
                            <img src="/static/cma/img/icon_trash2_hover.png" height="${icon_height}px" />
                        </div>
                    </div>
                </td>
            </tr>
        `);
    }
    
    // Update header_info 
    var nlayers = $('#datacube_layers tr.cube_layer').length - 1; // -1 b/c of instructions row 
    var s = nlayers == 1 ? '' : 's';
    var el = $('.header_info.datacube');
    el.html(`[${nlayers} layer${s} added]`);
    if (nlayers > 0) {
        el.removeClass('warning');
    } else {
        el.addClass('warning');
    }
}

function editProcessingSteps(cmp) {
    var tr = $(cmp).closest('tr');
    
    // Update layername 
    $('#processingsteps_layername').html(
        tr.attr('data-layername')
    );
    
    // Update datacube layer index 
    $('#processingsteps_layername').attr(
        'data-datacubeindex',
        tr.attr('data-datacubeindex')
    );
    
    // Empty current table
    $('#processingsteps_listtable tbody').html('');
    populateAddProcessingStep();
     
    // Load any existing processing steps
    $(cmp).find('tr').each(function(i,tr0) {
        var v = $(tr0).find('td').attr('data-value');
        onAddProcessingStep(v,PROCESSING_STEPS[v].name_pretty);
    });
   
    $('#datacube_processingsteps').show();
}

function onRemoveDataCubeLayerClick(cmp) {
    var tr = $(cmp).closest('tr');
    var layername = tr.attr('data-layername');
    
    // Update the "Add to cube" button 
    onRadioCubeClick($(`label[for='radiocube_${layername}'][class='no']`)[0]);//.trigger('click');
    
    // Remove table row
//     tr.remove();
    
}

function onCRSselect() {
    var crs_name = $('#cma_crs').val();
    var crs = CRS_OPTIONS[crs_name];
    $('#cma_crs_units').html(crs.units);
    $('#cma_resolution').val(crs.default_resolution);
    getFishnet();
}

function deleteTableRow(cmp) {
    $(cmp).closest('tr').remove();
}

function showProcessingStepParameters(el) {
//     console.log(el);
    var tr = $(el).closest('tr')
    var pstep = tr.attr('data-value');
    var psid = tr.attr('data-index');
    var psobj = PROCESSING_STEPS[pstep];

    
    // Update form title
    $('.parameters_form_title').html(psobj.name_pretty);
    $('.parameters_form_title').attr('data-parent_type','processingstep');
    $('.parameters_form_title').attr('data-parent_id',pstep);
    
    var dcid = $('#processingsteps_layername').attr('data-datacubeindex');

//     console.log(getParametersFromHTMLattrs(tr[0]));
    
    if (psobj.parameters) {
        buildParametersTable(
            psobj,
            '.parameters_form_table',
            getParametersFromHTMLattrs(tr[0])
        );
    }
    
    // Now show the modal interface
    $('.overlay.parameters_form').show();
    
}

function showModelParameters(el) {

    var tr = $(el).closest('tr')
    var pstep = tr.attr('data-value');
    var psid = tr.attr('data-index');
    var psobj = PROCESSING_STEPS[pstep];
    
    var model = MODELS[$('#model_select').val()];

    // Update form title
    $('.parameters_form_title').html(model.name_pretty);
    $('.parameters_form_title').attr('data-parent_type','model');
    $('.parameters_form_title').attr('data-parent_id',model.name);
      
    if (model.parameters) {
        buildParametersTable(
            model,
            '.parameters_form_table',
            null // <- input previously edit config data here
        );
    }
    
    // Now show the modal interface
    $('.overlay.parameters_form').show();
    
}

function onAddProcessingStep(v,lab) {
    v = v || $('#processingsteps_addstep').val();
    lab = lab || PROCESSING_STEPS[v].name_pretty;
    
    // TODO: load any params!
    
    // Looks in DATACUBE_CONFIG to see if there are any
    var layername = $('#processingsteps_layername').html();
    var dcid = $('#processingsteps_layername').attr('data-datacubeindex');
    
    // Index of the processing step
    var psid = $('#processingsteps_listtable tr').length;
    
    var params = '';
    if (DATACUBE_CONFIG[dcid].processingsteps[psid]) {
        $.each(DATACUBE_CONFIG[dcid].processingsteps[psid].parameters, function(p,v) {
                params += ` data-param__${p}="${v}"`;
            }
        );
    }
    
    var edit = '<td></td>';
    if (PROCESSING_STEPS[v].parameters) {
        edit = `
            <td class='edit' title='Edit step parameters'>
                <img onclick='showProcessingStepParameters(this);' 
                     height=14
                     src="/static/cma/img/form.svg" />
            </td>
        `;
        
    }
    
    $('#processingsteps_listtable tbody').append(`
        <tr data-value="${v}" data-index="${psid}" ${params}>
            ${edit}
            <td>${lab}</td>
            <td title='Delete processing step' class='delete' onclick="deleteTableRow(this);">x</td>
        </tr>
    `);
    
    // Re-populates the dropdown only w/ steps that have NOT been selected
    populateAddProcessingStep();
}

function getParametersFromHTMLattrs(el) {
    // el: raw html element (not jquery)
    // return json of key/value pairings
    params = {};
    $.each(el.attributes, function(i,attr) {
        if (attr.name.indexOf('param__') > -1) {
            params[attr.name.split('__')[1]] = attr.value;
        }
    });
    return params;
}

function onSaveProcessingSteps() {
    $('#datacube_processingsteps').hide();
    
    var layername = $('#processingsteps_layername').html();
    var dcid = $('#processingsteps_layername').attr('data-datacubeindex');
    
    // Reset everything
    DATACUBE_CONFIG[dcid].processingsteps = [];
    
    // Get list of steps from table
    var step_html = '<table>';
    $('#processingsteps_listtable tr').each(function(i,tr) {
        var step = $(tr).attr('data-value');
        
        // Get parameters
        params = getParametersFromHTMLattrs(tr);
        
        DATACUBE_CONFIG[dcid].processingsteps.push({name: step, parameters: params});
        step_html += `<tr><td data-value='${step}'>${PROCESSING_STEPS[step].name_pretty}</td></tr>`;
    });
    step_html += '</table>';
    $(`tr[data-layername='${layername}'] span.processingsteps_list`).html(step_html);
}


function updateSHPlabel(shp,el_id) {
    el_id = el_id || 'file_shp';
    var c = $(`label[for=${el_id}]`).find('span');
    c.removeClass('selected');
    if (shp) {
        c.html(shp);
        c.addClass('selected');
    } else {
        c.html('CHOOSE FILES');
    }
}

// detect a change in a file input with an id of “the-file-input”
$("#file_shp").change(function() {
    // will log a FileList object, view gifs below
    console.log(this.files);

    var shp, dbf;
    var submitButton = $('.modal_uploadshp tr.footer_buttons').find('.button.submit');
    var formData = new FormData($('#uploadForm')[0]);
    
    // Validate inputs
    var files_by_ext = {};
    $.each(this.files, function(i,file) {
        formData.append('file',file);
        var ext = file.name.split('.').pop();
        files_by_ext[ext] = file;
    });
    
    var exts = Object.keys(files_by_ext);
    var missing_exts = [];
    $.each(REQUIRED_SHP_EXTS, function(i,ext) {
        var extspan = $('.modal_uploadshp').find(`span.${ext}`);
        extspan.removeClass('allgood');
        if (!exts.includes(ext)) {
            missing_exts.push(ext);
        } else {
            extspan.addClass('allgood');
        }
    });
    if (missing_exts.length == 0) {
        submitButton.removeClass('disabled');
        updateSHPlabel(files_by_ext.shp.name);
            
    } else {
        submitButton.addClass('disabled');
        updateSHPlabel();
        
        return;
    }
    
});

// // detect a change in a file input with an id of “the-file-input”
// $("#file_geojson").change(function() {
//     // will log a FileList object, view gifs below
//     console.log(this.file);
// 
//     var submitButton = $('.modal_uploadgj tr.footer_buttons').find('.button.submit');
//     var formData = new FormData($('#uploadForm_gj')[0]);
//     
//     submitButton.removeClass('disabled');
//     updateSHPlabel(this.file.name,'file_geojson');
// });


function processGetAOIResponse(response,onEachFeature) {
//     clearDrawnLayers();
    
    var ds = JSON.parse(JSON.stringify(DRAW_STYLE));
    if (onEachFeature) {
        ds.pointerEvents = 'all';
    }
    var DRAWNLAYER;
    $.each(response.geojson, function(i,geojson) {
        DRAWNLAYER = L.geoJson(geojson,{
            style: ds,
            onEachFeature: onEachFeature,
        });
        drawnItems.addLayer(DRAWNLAYER);
        
    });
    
    return DRAWNLAYER;
    
}

function showInitializeCMAform() {
    $('.cma_start_div').hide();
    
    $('#cma_initialize_form').show();
    
    // Run validation
    validateCMAinitializeForm();
    
}
function showCMAstart() {
    $('.cma_start_div').show();
    
    $('#cma_initialize_form').hide();
    $('#cma_load_form').hide();
}

function getFishnet() {
    
    // Check to ensure the CMA CRS, spatial resolution, and extent are provided
    var res = $('#cma_resolution').val();
    var crs = $('#cma_crs').val();
    if (!res || !crs || !drawnLayer) {
        return;
    }
    
    if (AJAX_GET_FISHNET) {
        AJAX_GET_FISHNET.abort();
    }
    $('#cma_fishnet_message').hide()
    $('.loading_fishnet').show();
    FISHNET_LAYER.clearLayers();
    AJAX_GET_FISHNET = $.ajax('get_fishnet', {
        data: {
            resolution: res,
            srid: CRS_OPTIONS[crs].srid,
            extent_wkt: getWKT()
        },
        type: 'GET',
        success: function(response) {
            console.log(this.url,response);
            $('.loading_fishnet').hide();
            if (response.message) {
                $('#cma_fishnet_message').html(response.message);
                $('#cma_fishnet_message').show();
                return;
            }
            var gj = L.geoJSON(response.geojson, {
                style: {
                    weight: 0.5,
                    opacity: 0.9,
                    color: 'orange',
                },
//                 onEachFeature: function(feature,layer) {}
            });
            
            FISHNET_LAYER.addLayer(gj);
            

        },
        error: function(response) {
            console.log(response);
            alert(response.responseText);
            $('.loading_fishnet').hide()
        },
    });
    
}

function validateCMAinitializeForm(el) {
    console.log(el);
    if (el && ['cma_resolution','cma_crs'].indexOf($(el.target).attr('id')) > -1) {
        getFishnet();
    }
    
    var msg = '';
    
    // Name needs to be set and unique
    if ($('#cma_description').val() == '') {
        msg += "'CMA description' is not set<br>";
    }
    
    // TODO: check for name uniqueness
    
    // Mineral needs to be set 
    if ($('#cma_mineral').val() == '') {
        msg += "'CMA mineral' is not set<br>";
    }
    
    // Spatial res needs to be set 
    if ($('#cma_resolution').val() == '') {
        msg += "'Spatial res.' is not set'";
    }
    
    // Extent needs to be set
    if (!drawnLayer) {
        msg += "'Extent' is not set'";
    }
    
    // Now check if there's a message and disable/enable as needed
    if (msg) {
        $('#btn_cma_initialize_submit').addClass('disabled');
    } else {
        $('#btn_cma_initialize_submit').removeClass('disabled');
    }
    $('#cma_validate_message').html(msg);
}

function zeroPad(num, places) {
    var zero = places - num.toString().length + 1;
    return Array(+(zero > 0 && zero)).join("0") + num;
}

function getDateAsYYYYMMDD(dt) {
    dt = dt || new Date();
    return dt.getFullYear() + '-' + 
           zeroPad(dt.getMonth()+1,2) + '-' + 
           zeroPad(dt.getDate(),2);
}

function loadCMA() {
    // TODO: load it
    console.log('loading CMA eventually...');
}

function saveParametersForm() {
    
    var parent_type = $('.parameters_form_title').attr('data-parent_type');
    var parent_id = $('.parameters_form_title').attr('data-parent_id');
    var parent_id = $('.parameters_form_title').attr('data-parent_id');
    
    if (parent_type == 'processingstep') {
        // TODO: get layer
        var layer = $('#processingsteps_layername').html();
        console.log(parent_id);
        $.each(PROCESSING_STEPS[parent_id].parameters, function(i,group) {
            $.each(group, function(j,p) {
                var pname = `#${parent_id}__${p.name}`;
                var v = $(pname).val();
                $(`#processingsteps_listtable tr[data-value='${parent_id}']`).attr(
                    `data-param__${p.name}`,
                    $(pname).val()
                );
            });
        });
    }
    
    if (parent_type == 'model') {
        // TODO

        
    }
    
    $('.parameters_form').hide();
    
    
}

function initiateCMA() {
    console.log('initiating CMA eventually...');
    
    var cma_description = $('#cma_description').val();
    
    $('#cma_loaded').html(cma_description);
    $('#cma_loaded').removeClass('notactive');
    showCMAstart();
    
    $('#modeling_initial_message').hide();
    $('.model_select_div').show();
}


$('.modal_uploadshp tr.footer_buttons.load_aoi').find('.button.submit').on('click',function() {

    var shp, dbf;
    var formData = new FormData($('#uploadForm')[0]);

    $.each($('#file_shp')[0].files, function(i,file) {
        formData.append('file',file);
    });
                                                
    $('.modal_uploadshp').hide();
    if (AJAX_UPLOAD_SHAPEFILE) {
        AJAX_UPLOAD_SHAPEFILE.abort();
    }
//     AUDIO.submit.play();
    AJAX_UPLOAD_SHAPEFILE = $.ajax('get_shp_as_geojson', {
        processData: false,
        contentType: false,
        data: formData,
        type: 'POST',
        success: function(response) {
            console.log(this.url,response);
            
            // Reset upload form
            updateSHPlabel();
            $('.modal_uploadshp').hide();

            var e = $('#file_shp');
            e.wrap('<form>').closest('form').get(0).reset();
            e.unwrap();
            
            // Remove existing drawings before starting new one
            if (drawnLayer && MAP.hasLayer(drawnLayer)) {
                MAP.removeLayer(drawnLayer);
            }
            
            // Process new drawn layer
            drawnLayer = processGetAOIResponse(response);
//             drawnItems.addLayer(drawnLayer); // <<< this already gets added in processGetAOIResponse
            finishDraw(drawnLayer);
            
        },
        error: function(response) {
            console.log(response);
//             AUDIO.error.play();
            alert(response.responseText);
//             $('.submission_opts').show();
//             $('#burn_id_filter').show();
//             $('.modal_uploadshp').show();
//             $('.loading_user_submission').hide();
            
            updateSHPlabel();
        },
    });
});

//$('.modal_uploadgj tr.footer_buttons.load_aoi_gj').find('.button.submit').on('click',function() {
$('#file_geojson').on('change', function() {
    var formData = new FormData($('#uploadForm_gj')[0]);

    $.each($('#file_geojson')[0].files, function(i,file) {
        formData.append('file',file);
    });
                                    
    console.log(formData);
    $('.modal_uploadgj').hide();
    if (AJAX_UPLOAD_SHAPEFILE) {
        AJAX_UPLOAD_SHAPEFILE.abort();
    }
//     AUDIO.submit.play();
    AJAX_UPLOAD_SHAPEFILE = $.ajax('get_geojson_from_file', {
        processData: false,
        contentType: false,
        data: formData,
        type: 'POST',
        success: function(response) {
            console.log(this.url,response);
            
            // Reset upload form
            updateSHPlabel();
            $('.modal_uploadgj').hide();

            var e = $('#uploadForm_gj');
            e.wrap('<form>').closest('form').get(0).reset();
            e.unwrap();
            
            // Remove existing drawings before starting new one
            if (drawnLayer && MAP.hasLayer(drawnLayer)) {
                MAP.removeLayer(drawnLayer);
            }
            
            // Process new drawn layer
            drawnLayer = processGetAOIResponse(response);
//             drawnItems.addLayer(drawnLayer); // <<< this already gets added in processGetAOIResponse
            finishDraw(drawnLayer);
            
        },
        error: function(response) {
            console.log(response);
//             AUDIO.error.play();
            alert(response.responseText);
//             $('.submission_opts').show();
//             $('#burn_id_filter').show();
//             $('.modal_uploadshp').show();
//             $('.loading_user_submission').hide();
            
            updateSHPlabel();
        },
    });
});

onLoad();
