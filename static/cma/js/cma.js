// Interactive JS code for the CMA viewer/modeler

var WMS_URL;
var MAPFILE;

if (MAPSERVER_SERVER == 'vm-apps2') {
    WMS_URL = `https://apps2.mtri.org/mapserver/wms?`;
    MAPFILE = `/var/www/mapfiles/${MAPFILE_FILENAME}`;
} else if (MAPSERVER_SERVER == 'per440c') {
    WMS_URL = `http://opg.mtri.org/mapserver_opg/wms?`;
    MAPFILE = `/var/www/mapfiles2/${MAPFILE_FILENAME}`;
} else {
    WMS_URL = `https://${MAPSERVER_SERVER}/cgi-bin/mapserv?`;
    MAPFILE = `/var/www/mapfiles/${MAPFILE_FILENAME}`;
}
var COMMODITIES;
const REQUIRED_SHP_EXTS = ['shp','shx','prj','dbf'];
var images;
var drawnItems = new L.FeatureGroup();
var drawnLayer;
var extentPreviewLayer;
var DATACUBE_CONFIG = [];
var GET_MINERAL_SITES_RESPONSE_MOST_RECENT;
var GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT;
var GET_MODEL_RUNS_MOST_RECENT;
var MINERAL_SITES_LAYER;
var MINERAL_SITES_LAYER_USER_UPLOAD;
var CMAS_EXISTING;
var MINERAL_SITES_SORT_BY = {prop: 'id', order: 'asc'};
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

var PROCESSING_PARAMS_DESCS = {
    log: "Takes the log transform of the raster data",
    abs: "Takes the abs transform of the raster data",
    sqrt: "Takes the sqrt transform of the raster data",
    mean: "Missing values are imputed by the mean of raster data",
    median: "Missing values are imputed by the median of raster data",
    minmax: "Scales and translates raster data such that it is in the given range (0-1) on the training set",
    maxabs: "Scales each feature individually such that the maximal absolute value of each feature in the training set will be 1.0",
    standard: "Standardize features by removing the mean and scaling to unit variance"
};

// Cache for storing saved model parameters
var MODELS_CACHE;
resetModelCache();

function getSpecifyExtentTR(ignore) {
    var ig = '';
    if (ignore) {
        ig = `/ <label title='If checked, will query all of North America'>global <input type='checkbox' checked id='sites_ignoreextent' onchange='validateLoadSitesButton();'></label>`;
    }
    return `
        <td class='label'>Extent:</td>
        <td align='right'>
            <span class='link' onclick="$('#file_geojson').trigger('click')";">geojson</span> / <span class='link' onclick="$('.modal_uploadshp').show();">file</span> / draw: <a onClick=drawStart("polygon")>
            <img src="/static/cma/img/draw-polygon-icon.png" 
                height="17"
                id="draw_polygon_icon" /></a>
            <a onClick=drawStart("rectangle")>
            <img src="/static/cma/img/draw-rectangle-icon.png"
                height="17"
                id="draw_rectangle_icon" ></a>
            ${ig}
        </td>
    `;
}

const VECTOR_LEGENDS = {
    POINT: function(color, layername, w, h) {
        return `
            <pattern id="circles_${layername}" x="0" y="0" width="9" height="9" patternUnits="userSpaceOnUse">
                <circle fill="rgb(${color})" cx="2" cy="2" r="2"></circle>
                <circle fill="rgb(${color})" cx="7" cy="6" r="2"></circle>
            </pattern>
            <rect width="${w}" height="${h}" fill="url(#circles_${layername})" />
        `
    },
    LINE: function(color, layername, w, h) {
        return `
            <defs>
                <pattern id="diagonalHatch_${layername}" patternUnits="userSpaceOnUse" width="9.5" height="9.5" patternTransform="rotate(45)">
                    <line x1="0" y="0" x2="0" y2="9.5" stroke="rgb(${color})" stroke-width="3" />
                </pattern>
            </defs>
            <rect width="${w}" height="${h}" fill="url(#diagonalHatch_${layername})" />
        `
    },
    POLYGON: function(color, layername, w, h) {
        return `
            <rect width="${w}" height="${h}" fill="rgb(${color})" />
        `
    },
};


function copyJSON(json) {
    return JSON.parse(JSON.stringify(json));
}

function resetModelCache() {
    MODELS_CACHE = copyJSON(MODELS);
    
    // Now go through and set all SRI default values to null, per Angel Daruna's 
    // comment on Slack:
    // https://darpausgs.slack.com/archives/C05LT2E8YJY/p1727788832839669
    $.each(MODELS_CACHE, function(mname, mobj) {
        $.each(mobj.parameters, function(reqopt,groups) {
            $.each(groups, function(group,parr) {
                $.each(parr, function(i,p) {
                    p.value = p.html_attributes.value;
                    if (mname == 'sri_NN') {
                        p.value = null;
                    }
                });
            });
        });
    });


}

// Stuff to do when the page loads
function onLoad() {
    
    // Creates map layers from the datalayers lookup
    createMapLayers();
    
    // Add fishnet layer
    MAP.addLayer(FISHNET_LAYER);
    
    // Build map layer control
    createLayerControl();
        
    // Add top CMA choose control
    addCMAControl();
    
    // Add loading spinner controls
    addLoadingSpinnerControl('loading_fishnet','...loading grid preview');
    addLoadingSpinnerControl('loading_sites','...querying mineral sites');

    
    // Load CRS options
    var opts = ``;
    $.each(CRS_OPTIONS, function(crs,cobj) {

        var selected = crs == 'ESRI:102008' ? ' selected' : '';
//         console.log(crs,selected);
        opts += `<option value='${cobj.srid}'${selected}>${cobj.name}</option>`;
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
    
    // Populate ProcessingStep options
    populateAddProcessingStep();
    
    // Create legend control for mineral sites
    createLegendControl('legend_content_sites');
    
    // Create legend control for standard layers
    createLegendControl('legend_content','topright');
    
    // Add layers to layer control
    $.each(DATALAYERS_LOOKUP, function(dsid,dl) {
        addRowToDataLayersTable(dl);
    });
    
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
    $('#cma_crs').val("ESRI:102008");
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
//     toggleHeader($('#datalayer_container .header.toptop'));
//     toggleHeader($('#datalayer_container .header.Geophysics'));
    
    toggleHeader($('.header.modeling'));
    toggleHeader($('.header.datacube'));
    toggleHeader($('.header.training'));
    
    toggleHeader($('.header.model_outputs'));
    
    // Add listeners for KNOWN DEPOSIT SITES form
    $('.datalayer_table.known_deposit_sites input').on('change',validateLoadSitesButton);
    
    // Load extent specification tools to KNOWN DEPOSIT SITES
    $('#mineral_sites_extent_tr').html(getSpecifyExtentTR(true));
    
    // Create listeners for the upload data layer form
    $('#uploadForm_datalayer input').on('change', function() {
        validateUploadDataLayerForm();
    });
    
    // Add on click event for sorting by mineral site table headers
    $('.sites_sort_th td').on('click', function(e) {
        var sort_by = $(e.target).attr('data-prop');

        // Toggle sort order if same row was clicked
        if (MINERAL_SITES_SORT_BY.prop == sort_by) {
            MINERAL_SITES_SORT_BY.order = MINERAL_SITES_SORT_BY.order == 'asc' ? 'desc' : 'asc';
        }
        MINERAL_SITES_SORT_BY.prop = sort_by;

        loadMineralSitesToTable();
    });
    
    // Get metadata
    getMetadata();
}

function validateUploadDataLayerForm() {
   var fileinput = $('#file_datalayer');
   var filename = fileinput.val().split('\\').pop();
   
    updateSHPlabel(
        filename,
        'file_datalayer'
    );
    
    if ($('#uploaddl__description').val() == '') {
        $('#uploaddl__description').val(filename.split('.')[0]);
    }
    
    $('#uploadForm_datalayer .button.submit').removeClass('disabled');
    
//     function updateSHPlabel(shp,el_id) {
//     el_id = el_id || 'file_shp';
//     var c = $(`label[for=${el_id}]`).find('span');
//     c.removeClass('selected');
//     if (shp) {
//         c.html(shp);
//         c.addClass('selected');
//     } else {
//         c.html('CHOOSE FILES');
//     }

    // Validate inputs
//     var files_by_ext = {};
//     $.each(this.files, function(i,file) {
//         formData.append('file',file);
//         var ext = file.name.split('.').pop();
//         files_by_ext[ext] = file;
//     });
    
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
                    <div class='mpm_top_options'>
                        <span class='start_cma_link' onClick='showInitializeCMAform();'>initiate </span> | 
                        <span id="btn_cma_load" class='start_cma_link' onClick='showLoadCMAmodal();'>load</span> | <span id="btn_cma_clear" class='start_cma_link' onClick='clearCMA();'>clear</span>
                    </div>
                    <div class='mpm_top_active' title='Active Mineral Processing Model (MPM)'>
                        Active MPM:
                        <div id='cma_loaded' data-cma_id='' class='notactive'>-- none active --</div>
                    </div>
                </div>
                
                <div id="cma_initialize_form">
                    <div class='cma_navigate' onclick='showCMAstart();'>&#11178</div>
                    <div class='cma_initiate_title'>Initiate MPM</div>
                    <table id='cma_initialize_params' class='modeling_params'>
                        <tr>
                            <td class='label'>MPM mineral:</td>
                            <td><input type='text' id='cma_mineral' /></td>
                        </tr>
                        <tr>
                            <td class='label'>MPM description:</td>
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
                            <td>
                                <input type='number' id='cma_resolution' /><br>
                                <span class='link' style='color:#ffb366' onclick='loadCMAresolutionFromLayers();'>load min. from input layers</span>
                            </td>
                        </tr>
                        <tr>${getSpecifyExtentTR()}</tr>
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
//         console.log('stopping propagation');
        e.stopPropagation();
    });
    // This is for Safari browsers that for whatever reason pass the click 
    // through to the map instead of focusing on the input element
    $('.cma_header input').on('click', function(e) {
        $(e.target).focus();
    });
    
}

function loadCMAresolutionFromLayers() {
    var minres = 100000000;
    $.each(DATALAYERS_LOOKUP, function(l,obj) {
//         console.log(l,obj.spatial_resolution_m);
        if (obj.spatial_resolution_m != null) {
            minres = Math.min(minres, obj.spatial_resolution_m);
        }
    });
    
    $('#cma_resolution').val(minres);
    
}

function clearUserUploadSites() {
    // Remove map layer
    if (MAP.hasLayer(MINERAL_SITES_LAYER_USER_UPLOAD)) {
        MAP.removeLayer(MINERAL_SITES_LAYER_USER_UPLOAD);
    }
    
    // Hide tools
    $('#user_upload_sites_tools').hide();
    
    // Reset the "use" checkboxes so that queried sites are checked, uploaded 
    // are not
    $('#chk_use_sites_queried').prop('checked',true);
    $('#chk_use_sites_uploaded').prop('checked',false);
    
    // Reset the store
    GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT = null;
    
    // Reset initial instructions 
    $('#user_upload_sites_initial_instructions').show();
    
    updateNsitesLabels();
    
}

// Removes any queried KNOWN DEPOSIT SITES
function clearMineralSites() {
    // Remove map legend
    $('#legend_content_sites').html('');
    
    // Remove map layer
    if (MAP.hasLayer(MINERAL_SITES_LAYER)) {
        MAP.removeLayer(MINERAL_SITES_LAYER);
    }
    
    // Clear query results
    $('.mineral_sites_n_results').html('--');
    $('.mineral_sites_download_link').hide();
    
    // Add 'disabled' class back to clear button
    $('#clear_sites_button').addClass('disabled');
    
    // Add warning back to TRAINING DATA label
    // TODO: don't do this if there are user-uploaded sites loaded
    $('.header_info.training').addClass('warning');
    
    GET_MINERAL_SITES_RESPONSE_MOST_RECENT = null;
    updateNsitesLabels();
    
}

// Adds loading spinner control to map
function addLoadingSpinnerControl(div_class,message) {
    var Title = L.Control.extend({
        options: {
            position: 'topright'
        },

        onAdd: function () {
            var c = L.DomUtil.create('div', div_class);
            
            c.innerHTML = `${message} <div class='loading_spinner'></div>`;

            return c;
        }
    });
    var c = new Title();
    c.addTo(MAP);
}

// Capitalizes first letter of the given string
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}


// Builds the form that pops up when user clicks CONFIGURE MODEL PARAMETERS
// or when a user wants to edit processing step parameters
function buildParametersTable(mobj, table_selector, dobj) {
    var showhide_groups = {};
    var do_hypertune = mobj.name == 'sri_NN';
    var hypertune = '';
    var ptable_html = '<table class="model_parameters_table">';
    if (do_hypertune) {
        // If hypertune option, add header to table
        ptable_html += `
            <tr class='hypertune_labels' title="Choose 'customize to anually set the value for a parameter; if 'optimize' is selected, the value of the parameter will be determined via hyperparameter tuning" >
                <td></td>
                <td></td>
                <td>
                    <div class='rotate_container'><div class='rotate'>customize</div></div>
                    <div class='rotate_container' ><div class='rotate'>optimize</div></div>
                </td>
            </tr>
        `;
    }

    var range_double_params = {};
    $.each(['required','optional'], function(r,reqopt) {
        var obj = mobj.parameters[reqopt];
        
        if (!obj) {
            return;
        }
        
        if (reqopt == 'optional') {
            ptable_html += `
                <tr class='subcategory_label optional' onclick='toggleHeader(this);'>
                    <td><span class='collapse'>+</span> Advanced</td>
                    <td></td>
                    <td class='hypertune'></td>
                </tr>
            `;
        }
        
        var group_current;
        $.each(Object.keys(obj).sort(), function(g,group_name) {
            if (group_name != '_') {
                ptable_html += `
                    <tr class='subcategory_label' data-reqopt='${reqopt}'>
                        <td>${capitalizeFirstLetter(group_name)}</td>
                        <td></td>
                        <td class='hypertune'></td>
                    </tr>
                `;
            }
            $.each(obj[group_name], function(i,p) {
                var pid = `${mobj.name}__${p.name}`;
                if (p.only_show_with) {
                    var pshow = `${mobj.name}__${p.only_show_with}`;
                    if (!showhide_groups[pshow]) {
                        showhide_groups[pshow] = [];
                    }
                    showhide_groups[pshow].push(pid);
                }
                
                if (do_hypertune) {
                    // Create set of radio inputs
                    var cust_checked = ' checked';
                    var hyp_checked = '';
                    if (p.value == null) {
                        cust_checked = '';
                        hyp_checked = ' checked';
                    }
                    hypertune = `
                        <input type='radio' class='hypertune_input' name='hypertune_${pid}' value='customize'${cust_checked}>
                        <input type='radio' class='hypertune_input' name='hypertune_${pid}' value='hypertune'${hyp_checked}>
                    `;
                }
                
                var input_html;
                var input_td_attrs = '';
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
                    if (p.input_type == 'range') {
                        var attrs = p.html_attributes
                        var v = attrs.value;
                        
                        input_html = `
                            <span class='range_label'>${attrs.min}</span>${input_html}<span class='range_label'>${attrs.max}</span><input class='range_value' type='number' value=${v} />`;
//                         <div class='range_value'>${v}</div>
                        
                        input_td_attrs = ' class="input range_td"';
                        
                    }
                    if (p.input_type == 'range_double') {
                        range_double_params[p.name] = p;
                        input_html = `
                            <input type='number' id='${pid}__min' value=${p.html_attributes.value[0]}/>
                                <div id='range_double__${p.name}' class='range_double'></div>
                            <input type='number' id='${pid}__max' value=${p.html_attributes.value[1]} />`;
                    }
                } else { // for 'select' elements
                    var opts = '';
                    if (p.options) {
                        $.each(p.options, function(j,opt) {
                            var selected = '';
                            if (
                                 // If default has been modified, use that value
                                (dobj && opt == dobj[p.name]) ||
                                
                                // ...OR... if html_attributes has a default val 
                                (p.html_attributes && p.html_attributes.value == opt)
                            ) {
                                selected = ' selected';
                            }
                            let title="";
                            if (opt in PROCESSING_PARAMS_DESCS) {
                                title=` title=\"${PROCESSING_PARAMS_DESCS[opt]}\" `;
                            }
                            opts += `<option ${title}value="${opt}"${selected}>${opt}</option>`;
                        });
                    }
                    input_html = `
                        <select id="${pid}">
                            ${opts}
                        </select>
                    `;
                }
                
                ptable_html += `
                    <tr id="${pid}_tr"
                        title="${p.description}" 
                        data-reqopt='${reqopt}'>
                        <td class='label'>${p.name_pretty}:</td>
                        <td${input_td_attrs}><div class='input'>${input_html}</div></td>
                        <td class='hypertune'>${hypertune}</td>
                    </tr>
                `;
                
            }); // parameter loop
        }); // group loop
    }); // required/optional loop
    ptable_html += '<tr class="divider"></tr></table>';
    
    $(table_selector).html(ptable_html);
    
    if (do_hypertune) {
//         $('.parameters_form .model_parameters_table td div.input').hide();
        $('.parameters_form .model_parameters_table td.hypertune').show();
        
        $('input.hypertune_input').on('change', function(e) {
            var v = $(e.target).val();
            if (v == 'customize') {
                $(e.target).closest('tr').find('div.input').show();
            } else {
                $(e.target).closest('tr').find('div.input').hide();
            }
        });
        
        $('input.hypertune_input:checked').trigger('change');
    }
    
     // Toggle to hide advanced options
    $('tr[data-reqopt="optional"]').hide();
    
    // Create listeners for show/hide checkboxes
    $.each(showhide_groups, function(chk,ps) {
        $(`#${chk}`).on('change', function(e) {
            var checked = $(e.target).is(':checked');
            $.each(ps, function(i,p) {
                $(`#${p}_tr`).toggle(checked);
            });
        });
    });
    
    // Insert double sliders as needed
    $('.range_double').each(function(i,cmp) {
        if (Object.keys(range_double_params).length == 0) {
            return;
        }
        var pname = cmp.id.split('__')[1];
        var p = range_double_params[pname];
        var start_vals = p.html_attributes.value;

        if (!start_vals) {
            start_vals = [p.html_attributes.min,p.html_attributes.max];
        }
        if (!$(cmp).is(':empty')) {
            return;
        }

        noUiSlider.create(cmp, {
            range: {
                'min': p.html_attributes.min,
                'max': p.html_attributes.max,
            },
            step: p.html_attributes.step,
            start: start_vals,
//             margin: 300,
//             limit: 600,
            connect: true,
            direction: 'ltr',
            orientation: 'horizontal',
            behavior: 'drag',
//             pips: {
//                 mode: 'step',
//                 density: 4,
//                 
//             }
        });
        // When the slider value changes, update the input and span
        cmp.noUiSlider.on('update', function (values, handle) {
            $(handle).html(values[handle]);
            $('#range_diff-1').html(values[1] - values[0]);
            
            var prec = 2; // TODO: determine precision from scale
            $(cmp).next('input').val(Number(values[1]).toFixed(prec));
            $(cmp).prev('input').val(Number(values[0]).toFixed(prec));
        });
    });
    
    // Add listeners for type='range' to update the adjacent labels
    $('.model_parameters_table input[type="range"]').on('input', function(e) {
        var rng = $(e.target);
        rng.next('span.range_label').next('.range_value').val(rng.val());
    });
    
    // Add listeners for range labels to update the slider
    $('.model_parameters_table input.range_value').on('change', function(e) {
        var inp = $(e.target);
        inp.prev('span.range_label').prev('input[type="range"]').val(inp.val());
    });
}


// Resets model UI to starting point
// NOTE: the 'clear' arg was added to control whether or not to totally wipe
//       out the data cube selections and model config changes, BUT I'm not
//       sure there's a use-case for preserving these, so for now, everything
//       is cleared regardless and setting 'clear' has no effect.
function resetModelUI(clear) {
    $('.selected_model_config').hide();
    $('.collapse_datacube').hide();
    $('.collapse_training').hide();
    $('.collapse_parameters').hide();
    $('.collapse_model_run').hide();
    $('#modeling_buttons_table').hide();
    $('.radiocube').hide();
    $('#model_run_loaded .model_run_id').addClass('disabled');
    $('#model_run_loaded').hide();
    $('#model_run_loaded .model_run_id').html('[none loaded]');
    $('#model_run_edited').hide();

    
    
//     $('#model_select').val('');
    // Collapse results pane 
    closeCollapse('.header.model_results')
    
    if (clear) {
        clearModelUIselections();
    }
}

function showModelingMainPane() {
    $('#modeling_status_pane').hide();
    $('#modeling_main_pane').show();
    $('.mpm_top_options.modeling').show();
    
    
}

function clearModelUIselections(){ 
     $('#model_select').val('');
    
    // Clear datacube
    resetDataCube();
    
    // Reset model cache which returns the model parameter configurations to
    // default values
    resetModelCache();

    validateModelButtons();
    
}

function toggleLabelRasterEnable(toggle) {
    if (toggle == true) {
        $('#datacube_message_div').html('');
        $('tr.cube_layer.label_raster').removeClass('disabled');
    } else {
        $('tr.cube_layer.label_raster').addClass('disabled');
        $('#datacube_message_div').html(`
            <span class='lr_asterisk'>*</span> Label raster layer will only be used for label correlation analysis in unsupervised models
        `);
    }
}

// What happens when 'Select model type' changes
function onModelSelect() {
    var model = MODELS[$('#model_select').val()];
    
    // First hide everything
    resetModelUI();
    
    console.log(model, MODELS[$('#model_select').val()]);
    
    // Then build everything back up
//     $('.selected_model_description').html(model.description);
    $('#model_info .content').html(model.description);
    
    // Show CONFIG button
    $('.button.selected_model_config').show();
    
    // Show data cube builder interface
    if (model.uses_datacube) {
        $('.collapse_datacube').show();
    }
    $('.collapse_training').show();
    toggleLabelRasterEnable(true);
    if (model.uses_training == true) {

        $('tr.cube_layer.label_raster').removeClass('disabled');
    } else if (isLabelRasterInDataCube()) {
        // If a label raster is in the datacube and an unsupervised model is 
        // selected, gray it out 
        toggleLabelRasterEnable(false);
    }
    
    // Show selection buttons in Data Layers
    $('.radiocube').show();
    
    // Build parameters table 
    buildParametersTable(model,'.content.model');
    
    // Now trigger change to set initial display

    // Build buttons
    var button_html = '';
    $.each(model.buttons.buttons, function(i,button) {
        var onclick = button.onclick ? button.onclick : '';
        
        button_html += `
            <td class=${button.class}>
                <div class='button model_process_submit ${button.class}' onclick='${onclick};'>
                    ${button.label}
                </div>
            </td>`;
    });
    $('#modeling_buttons_table tr').html(button_html);
    
    // Show all sections
    $('.collapse_parameters').show();
    $('.collapse_model_run').show();
    $('#modeling_buttons_table').show();

    
    
    // Enable/disable buttons as needed
    validateModelButtons();

    
}

function onModelParameterCheckboxChange(cmp) {
    console.log(cmp);
}


function resetModelOutputs() {
    // Clear any model outputs associated w/ CMA 
    // ...but first remove any visible map layers
    $(`#outputlayer_container .collapse.sub tr td.show_chk input:checked`).trigger('click');
    $('#outputlayer_container .collapse.sub').remove();
    
  
    
//     $('#model_outputs_table').empty();
    
}

function resetProcessedLayers() {
      // Also clear processed layers 
    $(`#processedlayer_container .collapse.sub tr td.show_chk input:checked`).trigger('click');
    $('#processedlayer_container .collapse.sub').remove();
}

function clearCMA() {
    $('#cma_loaded').addClass('notactive');
    $('#cma_loaded').attr('data-cma_id','');
    $('#cma_loaded').html('--');
    
    $('#modeling_initial_message').show();
    $('#modeling_initial_message2').hide();
    $('.mpm_top_options.modeling').hide();
    
    $('.model_select_div').hide();

    resetModelOutputs();
    
    // Same with processed layers
    resetProcessedLayers();
    
    // Reset the Filter MPM outputs drop down
    $('#model_output_layers_filter select').html(
        '<option value="all" selected}>all</option>'
    );
    
    // Close any model outputs currently in the viewer
    // Hide "Choose existing MPM" modal
    $('#load_cma_modal').hide();
    
    resetModelUI(true);
    
    // Clear mineral sites
    clearMineralSites();
    
    // Clear extent
    if (drawnLayer && MAP.hasLayer(drawnLayer)) {
        MAP.removeLayer(drawnLayer);
    }
    
    $('#hide_intersecting_cb').prop('checked',false);
    $('.toggle_intersecting').hide();
    toggleIntersectingLayers();
}

// Performs various tasks to load a selected CMA into the GUI
function loadCMA(cma_id) {
    var cma = CMAS_EXISTING[cma_id];
    
    
    // Clear queried sites
    clearMineralSites();
    
    // Populate the InitiateCMA form
    $.each(['description','mineral','crs','resolution'], function(i,attr) {
        var a = cma[attr];
        if (attr == 'resolution') {a = a[0];}
        if (attr == 'crs') {a = a.split(':')[1];}
        $(`#cma_${attr}`).val(a);
    });

    // Populate KNOWN DEPOSIT SITES mineral
    var mineral = cma.mineral;
    if (mineral != 'rare earth elements') {
        mineral = capitalizeFirstLetter(mineral);
    }
    $('#commodity').val(mineral);
    
    // Change sites request limit to -1 so all sites are returned
    $('#mineral_sites_limit').val(-1);
    
    // Load extent
    // Remove existing drawings before starting new one
    if (drawnLayer && MAP.hasLayer(drawnLayer)) {
        MAP.removeLayer(drawnLayer);
    }
    drawnLayer = processGetAOIResponse({geometry:cma.extent});
    finishDraw(drawnLayer);

    // Make UI changes (show model opts, etc.)
    onStartedCMA(cma);
    
    // Load model runs
    loadModelRuns(cma_id);
    
    // Load known deposit sites
    loadMineralSites();
     
    // Clear loaded processed layers 
    resetProcessedLayers();  
    
     // Reset model outputs filter 
     $('#model_output_layers_filter select').val('all');
     // NOTE: vvv inititally load outputs; then check for others via "sync
//      Load outputs
    loadModelOutputs(cma_id,'all');
    
    syncModelOutputs(cma_id);
    
    // Show MODEL RESULTS section
    $('#outputlayer_container').show();
    $('#processedlayer_container').show();
    
}

// Loads outputs and processed layers to the layer control tables
function loadModelOutputs(cma_id,model_run_id) {
    cma_id = cma_id || getActiveCMAID();
    model_run_id = model_run_id || $('#model_output_layers_filter select').val();
    
    var cma = CMAS_EXISTING[cma_id];
    
    // First store which layers are visible
    var showing_outputs = $(`#outputlayer_container .collapse.sub tr td.show_chk input:checked`).closest('tr').map(function(i,tr) { return $(tr).attr('data-path');
    });
    
    // Remove existing content
    resetModelOutputs();

    var dls = [];
    $.each(DATALAYERS_LOOKUP, function(dsid,d) {
        var cats = getLayerControlCategories(d);
        d.category_sort = cats.category;
        d.subcategory_sort = cats.subcat;
        
        if (d.gui_model == 'outputlayer' && 
            d.cma_id && d.cma_id == cma_id &&
            (model_run_id == 'all' || (d.model_run_id && d.model_run_id == model_run_id))
        ) {
            // Don't add outputs from model run objects not loaded. 
            // Model runs are filtered by date to exclude early test runs, 
            // but outputs are not
            if (model_run_id != 'all' && (!cma.model_run_objects || !cma.model_run_objects[model_run_id])) {
                return;
            }
           
            dls.push(d);

        }
        
        // Also add processed layers
        if (d.gui_model == 'processedlayer' &&
            d.cma_id && d.cma_id == cma_id
        ) {
             dls.push(d);
        }
    });
    dls.sort(function(a,b) {
        if (a.category_sort == b.category_sort) {
            return a.subcategory_sort < b.subcategory_sort ? -1 : 1;
        }
        return a.category_sort < b.category_sort ? -1 : 1;
        
    });
    
    $.each(dls, function(i,d) {
        addRowToDataLayersTable(d);
    });
    
    // Toggle header to expand if model_run_id specified
    if (model_run_id != 'all') {
        toggleHeader($(`#outputlayer_container .header.topbar.sub`));
    }
    
    // Re-show the originally shown layers
    $.each(showing_outputs, function(i,dsid) {
        $(`#outputlayer_container tr[data-path="${dsid}"] td.show_chk input`).trigger('click');
    });
}

function downloadURLsToZip(urls, zipname, loading_container) {
     data = {
        urls: urls,
        zipname: zipname,
    };

    var lsid = 'outputs_bulk_download_spinner';
    loading_container.append(`<div id='${lsid}' class='loading_spinner'></div>`);
    
    // Use XMLHttpRequest instead of Jquery $ajax
    xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        var a;
        if (xhttp.readyState === 4 && xhttp.status === 200) {
            // Trick for making downloadable link
            a = document.createElement('a');
            a.href = window.URL.createObjectURL(xhttp.response);
            // Give filename you wish to download
            a.download = zipname;
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            $(`#outputs_bulk_download_spinner`).remove();
            a.remove();
        }
    };
    // Post data to URL which handles post request
    xhttp.open("POST", `/download_urls_to_zip`);
    xhttp.setRequestHeader("Content-Type", "application/json");
    // You should set responseType as blob for binary responses
    xhttp.responseType = 'blob';
    xhttp.send(JSON.stringify(data));
}

function downloadModelOutputsBulk(cmp) {
    var loading_container = $(cmp).parent();
    
    let dl_urls = [];
    $("#outputlayer_container .download a").each(function() {
        dl_urls.push($(this).attr('href'));
    });
    let cma_name = $("#cma_loaded")[0].innerText;
    var model_run_id = $('#model_output_layers_filter select').val();
    var zipname = model_run_id ? 
        `${cma_name}_${model_run_id}_outputs.zip` :
        `${cma_name}_outputs.zip` ;
    
   downloadURLsToZip(dl_urls,zipname,loading_container);
}

function downloadDataCubeLayers(cmp) {
    var loading_container = $(cmp).parent();
    
    var urls = DATACUBE_CONFIG.map(function(ds) {
        return DATALAYERS_LOOKUP[ds.data_source_id].download_url;
    });
   
    var zipname = `StatMaGIC_model_input_layers_${getDateAsYYYYMMDD(null,true)}.zip` ;
    
   downloadURLsToZip(urls,zipname,loading_container);
}

// Retrieves GUI metadata (e.g. list of existing CMAs/MPMs, commodity list)
// This does not get run until AFTER the page loads b/c it relies on queries to 
// CDR, and so even if the CDR is down or unresponsive, the page will still 
// load.
function getMetadata() {
    $.ajax(`${URL_PREFIX}get_metadata`, {
        data: {},
        success: function(response) {
            CMAS_EXISTING = response.cmas;
            
            // Load CMAs to load CMA table
            trs = '';
            $.each(CMAS_EXISTING, function(cma_id,cma) {
                trs += `
                    <tr onclick="loadCMA('${cma_id}');">
                        <td class='description'>${cma.description}</td>
                        <td>${cma.mineral}</td>
                        <td>${cma.resolution[0]}m</td>
                        <td>${cma.crs}</td>
                    </tr>
                `;
            });
            $('#choose_cma_table tbody').html(trs);
            
            // Now load these to the dropdowns
            $.each(['commodity','top1_deposit_type'], function(i,v) {
                var opts = v == 'commodity' ? '' : `<option value='' selected>[any]</option>`;
                $.each(response[v], function(i,c) {
                    var c0 = c == 'Rare earth elements' ? 'rare earth elements' : c;
                    opts += `<option value='${c0}'>${c}</option>`;
                });
                $(`#${v}`).html(opts);
            });
        },
        error: function(response) {
            console.log(response);
        }
    });
    
}

// Requests list of model runs for a given CMA_id from backend
function loadModelRuns(cma_id,mrid_selected) {
    $('#load_run_cma_label').html(CMAS_EXISTING[cma_id].description);
    $.ajax(`${URL_PREFIX}get_model_runs`, {
        data: {
            cma_id: cma_id,
        },
        success: function(response) {
            console.log(response);
            
            GET_MODEL_RUNS_MOST_RECENT = response.model_runs;
            
            // Load outputs
            loadModelOutputs(cma_id);
            processModelRunsFromCDR(response.model_runs,mrid_selected);

        },
        error: function(response) {
            console.log(response);
        }
    });
}

// Process updates to datalayers received from backend, e.g. when checking for 
function processDataLayersUpdates(response) {
    var dls_to_add = [];
    $.each(response.DATALAYERS_LOOKUP_UPDATES, function(dsid,dl) {
        if (!DATALAYERS_LOOKUP[dsid]) {
            dls_to_add.push(dl);
            DATALAYERS_LOOKUP[dsid] = dl;
            
//             console.log('adding layer: ',dsid);
            
            // Create WMS map layer so it can be loaded to map
            createMapLayer(dl.data_source_id,dl)
            
            // Add layer lookup 
            DATALAYERS_LOOKUP[dl.data_source_id] = dl;
            
            // TODO If it's a processed layer that is replacing a raw layer, update
            // the DATACUBE to reflect this
        }
    });
    
    // Add rows AFTER all new layers have been processed into DATALAYERS_LOOKUP
    // b/c some of the added layers may reference other layers (e.g. outputs or 
    // processed layers based on raw layers) that haven't been added yet.
    loadModelOutputs();
    $.each(dls_to_add, function(i,dl) {
        if (dl.gui_model == 'datalayer') {
            addRowToDataLayersTable(dl);
        }
    });
}

// Requests backend to check for any output layers that have not yet been
// sync'd w/ the GUI's PG database.
function syncModelOutputs(cma_id) {

    $.ajax(`${URL_PREFIX}sync_model_outputs`, {
        data: {
            cma_id: cma_id,
        },
        success: function(response) {
            console.log(response);
            
            // Update DATALAYERS_LOOKUP
            processDataLayersUpdates(response);
            
        },
        error: function(response) {
            console.log(response);
        }
    });
}

function getNlayersByEventID(event_id) {
    var n = 0;
    $.each(DATALAYERS_LOOKUP, function(dsid,l) {
        if (l.event_id && l.event_id == event_id) {
            n += 1;
        }
    });  
    return n;
}

function processNewProcessedLayer(l) {
    if (l.data_source_id_orig) {
        // Replace raw layer with processed layer in datacube
        onRadioCubeClick(
            $(`label[for='radiocube_${l.data_source_id_orig}'][class='no']`)[0]
        );
    }
    onRadioCubeClick(
        $(`label[for='radiocube_${l.data_source_id}'][class='yes']`)[0]
    );
    
}

function syncProcessedLayers(cma_id,awaiting_n_layers,event_id,run_model_on_complete) {

    $.ajax(`${URL_PREFIX}sync_processed_layers`, {
        data: {
            cma_id: cma_id,
            event_id: event_id,
        },
        success: function(response) {
            console.log(response);
            
            var n_event_layers_orig = getNlayersByEventID(event_id);
            
            var new_layers = [];
            $.each(response.DATALAYERS_LOOKUP_UPDATES, function(dsid,dl) {
                if (!DATALAYERS_LOOKUP[dsid]) {
                    new_layers.push(dl);
                }
            });
            
            // Update DATALAYERS_LOOKUP
            processDataLayersUpdates(response);
            
            // For some reason these seem to be hidden when added
            // dynamically
            $('.radiocube').show();
            
            // Process new layers 
            $.each(new_layers, function(i,l) {
                processNewProcessedLayer(l);
            });
            
            // Update status message
            var ts = getDateAsYYYYMMDD(null,true,true).split(' ');
            var sel0 = `.model_run_status_div[data-model_run_id="${event_id}"]`;
            var curmsg = $(`${sel0} td.status`).html();
            if (curmsg != response.model_run_status) {
                $(`${sel0} td.status`).html(response.model_run_status);
            }
             
            // Check to see if the # of existing layers for the event_id match 
            // the expected layers
            var n_event_layers = getNlayersByEventID(event_id);
            
            if (n_event_layers != n_event_layers_orig) {
                $('#message_modal_small .content').html(`
                    New processed layer available for event ID:<br><span class='highlight'>${event_id}</span>
                `);
                $('#message_modal_small').show();
                $(`#event_n_complete_${event_id}`).html(n_event_layers);
                $(`${sel0} td.last_updated`).html(`
                    <span class='date'>${ts[0]}</span>
                    <span class='time'>${ts[1]}</span>
                `)
            }
                      
            // Wait 3 seconds and then check again
            if (n_event_layers < awaiting_n_layers) {
                sleep(3000).then(() => {
                     syncProcessedLayers(
                         cma_id,
                         awaiting_n_layers,
                         event_id,
                         run_model_on_complete
                     );
                });
            } else {
                $('#model_run_status').removeClass('active');
                $(`${sel0} td.status`).html('Complete.');
                showModelingMainPane();
                if (run_model_on_complete) {
                    $('#message_modal_small .content').html(`
                        Pre-processing complete; submitting model run.
                    `);
                    $('#message_modal_small').show();
                    submitModelRun();
                }
            }
            
        },
        error: function(response) {
            console.log(response);
        }
    });
}

// From the return of the 'get_model_runs' endpoint, populates the 
// table that shows when "load an existing model run" is clicked
function processModelRunsFromCDR(model_runs,mrid_selected) {
    model_runs = model_runs || GET_MODEL_RUNS_MOST_RECENT;
    
    var trs = '';
    var all_sel = mrid_selected ? '' : ' selected';
    var opts = `<option value="all" ${all_sel}>all</option>`;
    var mrid_sort = Object.keys(model_runs).sort(function(a,b) {
        return model_runs[a].event.timestamp > model_runs[b].event.timestamp ? -1 : 1;
    });
    $.each(mrid_sort, function(i,mrid) {
        var mobj = model_runs[mrid];
        
//         console.log(mrid,mobj);
        
        // Skip model runs w/ zero evidence layers
        if (!mobj.event || mobj.event.payload.evidence_layers.length == 0) {
            return;
        }
        
        var cma = CMAS_EXISTING[mobj.cma_id];
        
        // Store model runs in the CMA object
        if (!cma.model_run_objects) {
            cma.model_run_objects = {};
        }
        cma.model_run_objects[mrid] = mobj;
        
        var n_outputs = 0;
        $.each(DATALAYERS_LOOKUP, function(dsid,d) {
            if (d.model_run_id && d.model_run_id == mrid) {
                n_outputs += 1;
            }
        });
        
        // WARNING: temporary! don't show model runs w/ no output layers
        //    * for demo purposes only; in practice users may want to
        //      load model runs that are IN PROGRESS
        // if (n_outputs == 0) { return;}
        
        var sys = mobj.system || '--';
        var sysv = mobj.system_version || '--';
//         console.log(opts_filter,mrid,opts_filter == 'all',opts_filter == mrid,opts_filter == 'all' || opts_filter == mrid);
//         if (opts_filter == 'all' || opts_filter == mrid) {
        trs += `
            <tr onclick="loadModelRun('${mobj.cma_id}','${mrid}')";>
                <td>${mrid}</td>
                <td>${cleanTimestamp(mobj.event.timestamp)}</td>
                <td>${sys}</td>
                <td>${sysv}</td>
                <td>${mobj.model_type}</td>
                <td>${mobj.event.payload.evidence_layers.length}</td>
                <td>${n_outputs}</td>
            </tr>
        `;
//         }
        //var sel = opts_filter == mrid ? ' selected' : '';
        var sel = mrid_selected == mrid ? ' selected' : '';
        opts += `
            <option value='${mrid}'${sel}>Model run: ${mrid} (${mobj.model_type},${cleanTimestamp(mobj.event.timestamp)}, ${n_outputs} outputs)</option>
        `;
        
    });

    $('#model_runs_table tbody').html(trs);
    $('#model_output_layers_filter select').html(opts);

}

// Empties the DATA CUBE
function resetDataCube() {
    DATACUBE_CONFIG = [];
    $.each(DATALAYERS_LOOKUP, function(dsid,obj) {
        onRadioCubeClick($(`label[for='radiocube_${dsid}'][class='no']`)[0]);
    });
    updateDataCubeLabelInfo();
}

// Loads model run to model UI and model cache
function loadModelRun(cma_id,model_run_id) {

    // Collapse deposit sites and prospectivity layers
    closeCollapse('.header.deposit_sites');
    closeCollapse('.header.toptop');
    
    $('#load_model_run').hide();
    $('#datalayer_info').hide();
    $('#modeling_initial_message2').hide();
    $('.model_select_div').show();
    
    var model_run = CMAS_EXISTING[cma_id].model_run_objects[model_run_id];
//     console.log(model_run);
    
    // Populate model config
    // Map of various model type vars to those listed in GUI
    var mtypemap = {
        beak_som: 'beak_som',
        som: 'beak_som',
        SOM: 'beak_som',
        sri_NN: 'sri_NN',
        'Neural Net': 'sri_NN',
        jataware_rf: 'jataware_rf',
    }
    var mtype = mtypemap[model_run.model_type];
    
    $('#model_select').val(mtype);
    onModelSelect();
    
     // Update Model run ID label
    $('#model_run_loaded .model_run_id').html(model_run_id);
    $('#model_run_loaded .model_run_id').removeClass('disabled');
    $('#model_run_loaded').show();
    
    $('.mpm_top_options.modeling').show();
    
    // Populate model config
    var train_config = model_run.event.payload.train_config;
    
    // Set any currently visible values
    $.each(train_config, function(p,v) {
//         console.log($(`#${mtype}__${p}`),v);
        $(`#${mtype}__${p}`).val(v);
    });
    
    // Update model cache
    $.each(MODELS_CACHE[mtype].parameters, function(reqopt,groups) {
        $.each(groups, function(group,parr) {
            $.each(parr, function(i,p) {
                p.value = train_config[p.name];
                // Only update the html_attribute default value if non-null
                if (p.value != null) {
                    p.html_attributes.value = p.value;
                    
                }
            });
        });
    });
    
    // Populate data cube
    // First clear existing datacube
    resetDataCube();
    
    var layers = model_run.event.payload.evidence_layers;
    $.each(layers, function(i,layer) {
        var dsid = layer.layer_id;//layer.data_source.data_source_id;
        var dl = DATALAYERS_LOOKUP[dsid];
        // TODO: current workaround for there not being non-tif data sources
        //       loaded yet; 
        if (dl) {
//             addLayerToDataCube(dl);
            
            // Update the 'Add to cube' interface
            onRadioCubeClick($(`label[for='radiocube_${dsid}'][class='yes']`)[0]);//.trigger('click');
        }
    });
    
    // Update the 'xx layers added' label
    updateDataCubeLabelInfo();
    
    // Change the Filter MPM outputs filter to that of the selected model_run_id
    $('#model_output_layers_filter select').val(model_run_id);
    loadModelOutputs();
    
}

function getModelRun(model_run_id,dl) {
    $.ajax(`${URL_PREFIX}get_model_run`, {
        data: {
            model_run_id: model_run_id,
        },
        success: function(response) {
            console.log(response);
            var meta = response.model_run;
            
            $('#model_run__type').html(meta.model_type);
            
//             $('#dl_model_run_metadata').html(`
//                 <span class='label'>Model run metadata:</span><br>
//                 Model type : ${meta.model_type}<br>
//                 
//             `);
            
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

function createMapLayer(name,obj) {
    obj.maplayer = L.tileLayer.wms(
        WMS_URL, {
            layers: name.replaceAll('.',''),
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
    
}

function createMapLayers() {
    $.each(DATALAYERS_LOOKUP, function(name,obj) {
        createMapLayer(name,obj);
    });
}

function showMessage(title,content) {
    $('#message_modal .message_modal_header').html(title);
    $('#message_modal .message_modal_content').html(content);
    
    $('#message_modal').show();
    
    
}

function createLayerControl() {
    var images2 = {Layers:{}};
    
    TA1_SYSTEMS = {};
    $.each(TA1_SYSTEMS,function(system, versions) {
        $.each(versions, function(i,version) {
            // Create a popup 
            var popup = L.popup({
                minWidth: 260,
                autoPan: false,
            });
            var ta1_layer = L.vectorGrid.protobuf(
                `https://api.cdr.land/v1/tiles/polygon/system/${system}/system_version/${version}/tile/{z}/{x}/{y}`, {
                fetchOptions: {
                    headers: {
                        Authorization: `Bearer ${CDR_BEARER}`
                    },
                },
                rendererFactory: L.svg.tile,//L.canvas.tile,// L.svg.tile
                attribution: system,
                interactive: true,
                vectorTileLayerStyles: {
                    units: function(properties) {
                        return {
                            weight: 0.5,
                            color: properties.color,
                            fillColor: properties.color,
                            fillOpacity: 0.5,
                            fill: true,
                        };
                    },
                    lines: function(properties) {
                        return {
                            weight: 1,
                            color: properties.color,
                        };
                    }
                },
            });
            ta1_layer.bindPopup(popup);
            ta1_layer.on('click', function(e) {
                var prop = e.layer.properties;
                console.log(prop);
                popup.setContent(`${prop.system} v${prop.system_version}<br><b>${prop.descrip}</b>`);
                ta1_layer.openPopup();
            });
        //     ta1_layer.on('mouseover', function(e) {
        //         console.log(e.layer);
        // //         e.layer.setStyle({weight: 1});//, fillOpacity: 0.7});
        // 
        //         
        //     });
            
            images2.Layers[`ta1__${system}_v${version}`] = {
                group: 'Reference Layers',
                label: `TA1 ${system} v${version}`,
                as_checkbox: true,
                title: '',
                layers: [ta1_layer],
                legend: '',
            };
        });
    });
    
     // Create a popup 
    var popup2 = L.popup({
        minWidth: 260,
        autoPan: false,
    });
    var macrostrat_layer_units = L.vectorGrid.protobuf(
        'https://dev.macrostrat.org/tiles/carto/{z}/{x}/{y}', {
        attribution: 'Macrostrat',
        interactive: true,
        vectorTileLayerStyles: {
            units: function (properties) {
                return {
                    weight: 0.1,
                    color: properties.color,
                    fillColor: properties.color,
                    fillOpacity: 0.5,
                    fill: true,
                };
            },
            lines: {
                weight: 0,
                
            }
        },
    });
    macrostrat_layer_units.bindPopup(popup2);
    macrostrat_layer_units.on('click', function(e) {
        var prop = e.layer.properties;
        
        // Special parsing of the 'lith' property b/c sometimes it's just a
        // list and sometimes it's divided between Major/Minor/etc.
        var lith = prop.lith;
        if (lith.indexOf('Major') > -1) {
            lith = lith.replaceAll('{',' ').replaceAll('},','}');
            if (lith.slice(-1) == '}') {
                lith = lith.slice(0,-1);
            }
            lith = lith.split('}');
        } else {
            lith = lith.split(',');
        }
    
        var desc = prop.descrip ? `<span class='link' onclick="showMessage('${prop.name} - description','${prop.descrip}');">Description</span>` : '';
    
        popup2.setContent(`
            <b>${prop.name}</b>
            <br><br>
            <span class='label'>Age:</span> <b>${prop.age}</b><br>
            <span class='label'>Best age (top):</span> <b>${prop.best_age_top.toFixed(1)}</b><br>
            <span class='label'>Best age (bottom):</span> <b>${prop.best_age_bottom.toFixed(1)}</b><br>
            ${desc}
            <br><br>
            <span class='label'>Lithology:</span><br><span class='emri_keyword'>${lith.join('</span><span class="emri_keyword_break"> | </span><span class="emri_keyword">')}</span>
            <br><br>
            <span class='label'>Comments:</span>
            <div class='macrostrat_source'>${prop.comments}</div>
            <br><br>
            <span class='label'>Source:</span><br>
            <div class='macrostrat_source'><a href='${prop.ref_url}' target='_blank' >${prop.ref_authors} ${prop.ref_year}. ${prop.ref_title}. ${prop.ref_source}. ${prop.ref_isbn}</a>
            </div>
            <br>
            
            
        `);
        console.log(e.layer.properties);
        macrostrat_layer_units.openPopup();

    });
    macrostrat_layer_units.on('mouseover', function(e) {
        e.layer.setStyle({fillOpacity: 0.9});
    });
    macrostrat_layer_units.on('mouseout', function(e) {
        e.layer.setStyle({fillOpacity: 0.5,});
    });
    
     // Create a popup 
    var popup = L.popup({
        minWidth: 260,
        autoPan: false,
    });
    var macrostrat_layer_lines = L.vectorGrid.protobuf(
        'https://dev.macrostrat.org/tiles/carto/{z}/{x}/{y}', {
        attribution: 'Macrostrat',
        interactive: true,
        vectorTileLayerStyles: {
            units: {
                fillOpacity: 0,
                weight: 0,
            },
            lines: {
                weight: 1,
                color: '#222',
            }
        },
    });
    
    images2.Layers.macrostrat_units = {
        group: 'Reference Layers',
        label: 'Macrostrat - units',
        as_checkbox: true,
        title: '',
        layers: [macrostrat_layer_units],
        legend: '',
    };
    images2.Layers.macrostrat_lines = {
        group: 'Reference Layers',
        label: 'Macrostrat - lines',
        as_checkbox: true,
        title: '',
        layers: [macrostrat_layer_lines],
        legend: '',
    }
    
    
    // Mapping of 'program' property to color, as used in: https://ngmdb.usgs.gov/emri/#20041
    var emri_color_map = {
        'reconnaissance geochemistry': '#ed6192',
        'geological Mapping': '#e5975e',
        'geologic mapping': '#e5975e',
        'geophysics': '#1d8da2',
        'lidar': '#9c84a3',
        'hyperspectral': '#807e3f',
        '3d geological model': '#803f60',
        'mine waste': '#254434',
    }
    
    function parseEMRIprogram(properties) {
        return JSON.parse(properties.program)[0].toLowerCase();//properties.program.slice(2,-2).split(',')[0].replace('"','').toLowerCase();
    }
     // Create a popup 
    var popup = L.popup({
        minWidth: 260,
        autoPan: false,
    });
    var emri_layer = L.vectorGrid.protobuf(
        'https://api.mapbox.com/v4/cgarrity.273objnx/{z}/{x}/{y}.vector.pbf?sku=101MMCEfKe5HO&access_token=pk.eyJ1IjoiY2dhcnJpdHkiLCJhIjoiM1RMUGpLcyJ9.jZ7CdJD_QpjsRuygD4un7w', {
        fetchOptions: {
            headers: {
//                 Authorization: `Bearer ${CDR_BEARER}`
            },
        },
        rendererFactory: L.svg.tile,//L.canvas.tile,// L.svg.tile
        attribution: 'Earth MRI',
        interactive: true,
        vectorTileLayerStyles: {
            'acquisitions-1ug54m': function(properties) {
                return {
                    weight: 0.5,
                    color: '#cccccc',
                    fillColor: emri_color_map[parseEMRIprogram(properties)],
                    fillOpacity: 0.5,
                    fill: true,
                };
            },
        },
    });
    emri_layer.bindPopup(popup);
    emri_layer.on('click', function(e) {
        console.log(e.layer.properties);
        var prop = e.layer.properties;
        var contact = JSON.parse(prop.contact)[0];
        console.log(contact);
        popup.setContent(`
            <b>${prop.alias}</b> | ${prop.affiliatio} | <b>${parseEMRIprogram(prop)}</b>
            <br><br>
            <span class='label'>Year started:</span> <b>${prop.yearstart}</b>
            <br><br>
            <span class='label'>Contact name:</span> <b>${contact.cname}</b><br>
            <span class='label'>Contact email:</span> <b>${contact.cmail}</b><br>
            <a href='${prop.website}' target='_blank'>Website</a> | <a href='https://mrdata.usgs.gov/earthmri/data-acquisition/project.php?f=html&pid=${prop.pid}' target='_blank'>More info</a>
            <br><br>
            <span class='label'>Keywords:</span><br><span class='emri_keyword'>${prop.pkeyword.split(';').join('</span><span class="emri_keyword_break"> | </span><span class="emri_keyword">')}</span>
            
        `);
        emri_layer.openPopup();
    });
    
    images2.Layers.emri_layer = {
        group: 'Reference Layers',
        label: 'Earth MRI Acquisitions',
        as_checkbox: true,
        title: '',
        layers: [emri_layer],
        legend: '',
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
        map: '/var/www/mapfiles2/statmagic.map',
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
        $('.toggle_intersecting').hide();
        $('#hide_intersecting_cb').prop('checked',false);
        toggleIntersectingLayers();
    });
}

function finishDraw(layer) {
    // Zoom to drawn polygon
    MAP.fitBounds(layer.getBounds(),{padding: [80,80]});
    
    // TODO: If this drawing is for mineral sites:
    
    // Enable/disable load sites button
    validateLoadSitesButton();
    
    // TODO: If this drawing comes from CMA:
//     getFishnet();
    
    // Validate CMA initialization form
    validateCMAinitializeForm();

    // Show the checkbox for toggling by extent intersection
    $('.toggle_intersecting').show();
    
    toggleIntersectingLayers();
}

function getMineralSitesRequestFilters() {
    var rank = [];
    $('.dedup_chk.rank:checked').each(function(i,chk) {
        rank.push(chk.id.split('__')[1]);
    });
    
    var types = [];
    $('.dedup_chk.type:checked').each(function(i,chk) {
        types.push(chk.id.split('__')[1].replace('_',' '));
    });
    
    var ignore_extent = $('#sites_ignoreextent').is(':checked') || !drawnLayer;
    var wkt = ignore_extent ? null : getWKT();
    
    return {
        top1_deposit_type: $('#top1_deposit_type').val(),
        top1_deposit_classification_confidence__gte: $('#top1_deposit_classification_confidence__gte').val(),
        commodity: $('#commodity').val(),
        only_gradetonnage: $('#only_gradetonnage').is(':checked'),
        rank: rank.join(','),
        type: types.join(','),
        limit: $('#mineral_sites_limit').val(),
        wkt: wkt,
    }
    
    
}

function loadMineralSites() {
    // Request the selected sites
    
    // First abort any requests to the same endpoint that are in progress
    if (AJAX_GET_MINERAL_SITES) {
        AJAX_GET_MINERAL_SITES.abort();
    }
    
    setLoadingLoadSitesButton();
    
    
    AJAX_GET_MINERAL_SITES = $.ajax(`${URL_PREFIX}get_mineral_sites`, {
        data: JSON.stringify(getMineralSitesRequestFilters()),
        type: 'POST',
        dataType: 'json',
        contentType: 'application/json; charset=utf-8',
        success: function(response) {
//             console.log(response);
            GET_MINERAL_SITES_RESPONSE_MOST_RECENT = response;
            
            // Add 'exclude' property to each site
            $.each(GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites, function(i,s) {
                s.properties.exclude = false;
            });
            
            // Add points to map
            loadMineralSitesToMap();
            
            // Load mineral sites to table
            loadMineralSitesToTable();
            
            // Remove 'clear sites' button disabled class
            $('#clear_sites_button').removeClass('disabled');
            
            // Update query results n

            updateNsitesLabels();
            $('.mineral_sites_download_link').show();
            
            // Update TRAINING_DATA warning class 
            if (response.mineral_sites.length > 0) {
                $('.header_info.training').removeClass('warning');
            } else {
                $('.header_info.training').addClass('warning');
            }
            
            enableLoadSitesButton();
            
        },
        error: function(response) {
            console.log(response);
            enableLoadSitesButton();
        }
    });
    
}

function toggleUserUploadSitesVisibility(e) {

    if ($('#user_upload_sites_show').is(':checked')) {
        MINERAL_SITES_LAYER_USER_UPLOAD.addTo(MAP);
    } else {
        // Remove current layer if it exists
        if (MAP.hasLayer(MINERAL_SITES_LAYER_USER_UPLOAD)) {
            MAP.removeLayer(MINERAL_SITES_LAYER_USER_UPLOAD);
        }
    }
}

function updateNsitesLabels() {
    var n_included = 0;
    if (GET_MINERAL_SITES_RESPONSE_MOST_RECENT && 
        $('#chk_use_sites_queried').is(':checked')) {
    
        $('.mineral_sites_n_results').html(
            GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites.length
        );
        
        // Update the '.mineral_sites_n_results.training' spans
        n_included= GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites.reduce(function(total,s) {
            return total + !s.properties.exclude;
        }, 0);
    }
    
    var n_total = n_included;
    if (GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT &&
        $('#chk_use_sites_uploaded').is(':checked')
    ) {
        var n_upload_sites = GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT.site_coords.length
        
        // Add any user-uploaded sites
        n_total += n_upload_sites;
        
         // Update user upload label
        $('.n_user_upload_sites').html(n_upload_sites);
        
        $('#training_data_user_sites_label').show();
        
    } else {
        $('.n_user_upload_sites').html('--');
        $('#training_data_user_sites_label').hide();
    }
        
    $('.mineral_sites_n_included').html(n_included);
    $('.mineral_sites_n_results.training').html(n_total);
    
    if (n_total == 0) {
        $('.header_info.training').addClass('warning');
    } else {
        $('.header_info.training').removeClass('warning');
    }
    
    if (GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT) {
        $('.n_user_upload_sites.main_label').html(n_upload_sites);
    }
}

function setLoadingLoadSitesButton() {
    // Show loading spinner
    $('.loading_sites').show();
    
    // Temporarily disable the "load sites" button
    setLoadingButton('load_sites_button');
}

function enableLoadSitesButton(btn_id,label) {
    $('.loading_sites').hide();
    resetButton('load_sites_button','Load/refresh');
    resetButton('show_histogram_button','Tonnage histogram');
}

function setLoadingButton(btn_id) {
    $(`#${btn_id}`).addClass('disabled');
    $(`#${btn_id}`).html("loading <div class='loading_spinner'></div>");
    
}

function resetButton(btn_id,label) {
    $(`#${btn_id}`).removeClass('disabled');
    $(`#${btn_id}`).html(label);
}

function downloadMineralSites(format) {
    format = format || 'shp';
    // Request the selected sites
    
    // First abort any requests to the same endpoint that are in progress
    if (AJAX_GET_MINERAL_SITES) {
        AJAX_GET_MINERAL_SITES.abort();
    }
    
   setLoadingLoadSitesButton();
    
    var data = getMineralSitesRequestFilters();
    data.format = format;
    
    var ext = format == 'shp' ? 'zip' : format;
    
    // Use XMLHttpRequest instead of Jquery $ajax
    xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        var a;
        if (xhttp.readyState === 4 && xhttp.status === 200) {
            // Trick for making downloadable link
            a = document.createElement('a');
            a.href = window.URL.createObjectURL(xhttp.response);
            // Give filename you wish to download
            a.download = `StatMAGIC_${data.commodity}_${getDateAsYYYYMMDD(null,true)}.${ext}`;
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            
            enableLoadSitesButton();
        }
    };
    // Post data to URL which handles post request
    xhttp.open("POST", `/get_mineral_sites`);
    xhttp.setRequestHeader("Content-Type", "application/json");
    // You should set responseType as blob for binary responses
    xhttp.responseType = 'blob';
    xhttp.send(JSON.stringify(data));
}

function getCommodityAndDTsFromSite_old(site_prop) {
    var commodities = [];
    $.each(site_prop.mineral_inventory, function(i,m) {
        if (commodities.indexOf(m.commodity) == -1) {
            commodities.push(m.commodity);
        }
    });
    var dtcs = [];
    var dtcs_w_conf = [];
    $.each(site_prop.deposit_type_candidate, function(i,m) {
        if (dtcs.indexOf(m.observed_name) == -1) {
            dtcs.push(m.observed_name);
            dtcs_w_conf.push({name: m.observed_name, conf: m.confidence});
        }
    });
    if (dtcs_w_conf.length == 0) {
        dtcs_w_conf = [{name: '--', conf: ''}];
    }
    
    return {
        commodities: commodities,
        dtcs: dtcs,
        dtcs_w_conf: dtcs_w_conf,
    };
}

function getCommodityAndDTsFromSite(site_prop) {
    var commodities = [];
//     $.each(site_prop.mineral_inventory, function(i,m) {
    if (commodities.indexOf(site_prop.commodity) == -1) {
        commodities.push(site_prop.commodity);
    }
//     });
    var dtcs = [];
    var dtcs_w_conf = [];
//     $.each(site_prop.deposit_type_candidate, function(i,m) {
    if (dtcs.indexOf(site_prop.top1_deposit_type) == -1) {
        dtcs.push(site_prop.top1_deposit_type);
        dtcs_w_conf.push({name: site_prop.top1_deposit_type, conf: site_prop.top1_deposit_classification_confidence});
    }
//     });
    if (dtcs_w_conf.length == 0) {
        dtcs_w_conf = [{name: '--', conf: ''}];
    }
    
    return {
        commodities: commodities,
        dtcs: dtcs,
        dtcs_w_conf: dtcs_w_conf,
    };
}

function maybeArrToStr(n) {
    if (!n) {return '';}
    return n.charAt(0) == '[' ? JSON.parse(n) : [n];
}

function loadMineralSitesToTable() {
//     sort_by = sort_by || 'id';
    var sort_by = MINERAL_SITES_SORT_BY.prop;

    // First clear out existing rows
    $('#sites_tbody').empty();
    
    var sites = GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites.sort(function(a,b){
        v0 = MINERAL_SITES_SORT_BY.order == 'asc' ? 1 : -1;
        v1 = v0 == 1 ? -1 : 1;
        var aprop = a.properties;
        var bprop = b.properties;
        var av = aprop[sort_by];
        var bv = bprop[sort_by];
        
        if (a === b) {
            return 0;
        }
        
        if (av === null || av == false) {
            return v0;
        }
        if (bv === null || bv == false) {
            return v1;
        }

        return av > bv ? v0 : v1;
    })
//     console.log(sites);
    
    var trs = '';
    $.each(sites, function(i,mobj) {
       // var bg_color = i % 2 == 0 ? 'rgb(64, 64, 64)' : 'rgb(57, 57, 57);';
        var evenodd = i % 2 == 0 ? 'even' : 'odd';
        var m  = mobj.properties;
        var msids = maybeArrToStr(m.mineral_site_ids);
        var names = maybeArrToStr(m.names);
        var types = maybeArrToStr(m.type);
        var ranks = maybeArrToStr(m.rank);
        var rowspan = msids.length > 3 ? 4 : msids.length;//Math.min(names.length+1,4);
        //var srcs = getMineralSiteSourcesTable(m);
        var conf = m.top1_deposit_classification_confidence;
        if (conf) {
            conf = conf.toFixed(1);
        } else {
            conf = '--';
        }
        
        var src_style = msids.length == 1 ? ' style="border-bottom: none;"' : '';
        var top1_src = m.top1_deposit_classification_source;
        top1_src = top1_src ? `${top1_src.slice(0,12)} [...]` : '--';
        
        var exclude = m.exclude ? ' checked' : '';
        
        trs += `
        <tr class='${evenodd}' id='site_tr_${m.id}'>
            <td class='exclude sites_table_exclude_td' rowspan=${rowspan}><input type='checkbox'${exclude} onclick='toggleExcludeChk("${m.id}");' /></td>
            <td class='id' rowspan=${rowspan}>${m.id}</td>
            <td class='commodity' rowspan=${rowspan}>${m.commodity}</td>
            <td class='sources'${src_style}><a href='${getMineralSiteSourceLink(msids[0])}' target='_blank'>${names[0] || '--'}</a></td>
            <td class='sources rank'${src_style}>${types[0] || 'NotSpecified'}</td>
            <td class='sources type'${src_style}>${ranks[0] || '--'}</td>
            <td class='break' rowspan=${rowspan}></td>
            <td class='dt_data' rowspan=${rowspan}>${m.top1_deposit_type || '--'}</td>
            <td class='dt_data' rowspan=${rowspan}>${m.top1_deposit_group || '--'}</td>
            <td class='dt_data' rowspan=${rowspan}>${m.top1_deposit_environment || '--'}</td>
            <td class='dt_data conf' rowspan=${rowspan}>${conf}</td>
            <td class='dt_data'
                title='${m.top1_deposit_classification_source}'
                rowspan=${rowspan}>
                ${top1_src}
            </td>
        </tr>
        `;
        for (let i = 1; i < msids.length; i++) {
            cls = i > 2 ? `site_src_row_extra ${m.id}` : '';
            var style = i == msids.length - 1 ? ' style="border-bottom: none;"' : '';
            trs += `
                <tr class='${cls} ${evenodd}'>
                    <td class='sources'${style}>
                        <a href='${getMineralSiteSourceLink(msids[0])}' target='_blank'>${names[i] || '--'}</a>
                    </td>
                    <td class='sources rank'${style}>${types[i] || 'NotSpecified'}</td>
                    <td class='sources type'${style}>${ranks[i] || '--'}</td>
                </tr>
            `;
            
            // After the third source, if any remain, hide under expandable
            // row
            if (i == 2 && msids.length > 3) {
                
                trs += `
                <tr class='${evenodd}'>
                    <td colspan=3 class='site_src_toggle_tr ${m.id}' onclick='toggleAllSiteSources("${m.id}",${msids.length});'>
                        + show all ${msids.length} sources for this site
                    </td>
                </tr>
                `;
            }
            
        }
    });
    $('#sites_tbody').append(trs);
}

function toggleAllSiteSources(mid,n_srcs) {
    var td = $(`.site_src_toggle_tr.${mid}`);

    if (td.html().indexOf('+') > -1) {
        td.html('- collapse full sources list');
        $(`.site_src_row_extra.${mid}`).show();
        $(`#site_tr_${mid} td`).not('.sources').attr('rowspan',n_srcs+1);
    } else {
        td.html(`+ show all ${n_srcs} sources for this site`);
        $(`.site_src_row_extra.${mid}`).hide();
        $(`#site_tr_${mid} td`).not('.sources').attr('rowspan',Math.min(n_srcs+1,4));
    }
}

function getMineralSiteSourceLink(mineral_site_id) {
    var reclink = mineral_site_id;
    if (mineral_site_id.indexOf('mrdata') > -1) {
        var record_id = mineral_site_id.split('__').slice(-1)[0];
        reclink = `https://mrdata.usgs.gov/mrds/show-mrds.php?dep_id=${record_id}`
    } 
    return reclink
}

function getMineralSiteSourcesTable(prop) {
    var src = `
        <table class='model_parameters_table mineral_site_info_table sources'>
            <tr>
                <td class='colname'>Name</td>
                <td class='colname'>Type</td>
                <td class='colname'>Rank</td>
            </tr>
    `;
    var names = maybeArrToStr(prop.names);
    var msids = maybeArrToStr(prop.mineral_site_ids);
    var ranks = maybeArrToStr(prop.rank);
    var types = maybeArrToStr(prop.type);
    $.each(msids, function(i,msid) {
//         var reclink = msid;
//         if (msid.indexOf('mrdata') > -1) {
//             var record_id = msid.split('__').slice(-1)[0];
//             reclink = `https://mrdata.usgs.gov/mrds/show-mrds.php?dep_id=${record_id}`
//         } else {
//             reclink = msid;
//             
//         }
        var reclink = getMineralSiteSourceLink(msid);
        var name = names[i] || '--';
        var type = types[i] || 'NotSpecified';
        var rank = ranks[i] || '--';

        src += `
            <tr>
                <td><a href=${reclink} target='_blank'>${name}</a></td>
                <td class='type'>${type}</td>
                <td class='rank'>${rank}</td>
            </tr>
        `;
    });
    src += '</table>';
    
    return src;
    
}

            
function toggleExcludeChk(id) {

    $.each(GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites, function(i,s) {
        if (s.properties.id == id) {
            s.properties.exclude = !s.properties.exclude//$('#site_popup_exclude_chk').is(':checked');
            return false;
        }
    });
    
    updateNsitesLabels();
    
    // Reset display (in case 'included in training' is selected
    onMineralSitesDisplayByChange();
}
        

function loadMineralSitesToMap() {
    
    // Remove current layer if it exists
    if (MAP.hasLayer(MINERAL_SITES_LAYER)) {
        MAP.removeLayer(MINERAL_SITES_LAYER);
    }
    
    // Create new layer
    MINERAL_SITES_LAYER = L.geoJSON(
        GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites,{

        pointToLayer: function(feature,latlng) {
            return L.circleMarker(latlng,{
                radius: 6,
                fillOpacity: 0.9,
                opacity: 1,
                color: '#000',
                weight: 0.5,
                className: 'mineral_site_marker',
            });
        },
        onEachFeature: function(feature,layer) {
            var popup = L.popup({
                minWidth: 260,
                autoPan: false,
            });

            layer.bindPopup(popup);
        }
    });
    
    // Create a popup to use in the macrostrat layer
    MINERAL_SITES_LAYER.on('mouseover', function(e) {
        e.layer.setStyle({radius: 10});
    });
    MINERAL_SITES_LAYER.on('mouseout', function(e) {
        e.layer.setStyle({radius: 6});
        
        // vvv commenting this out for now b/c this is erasing the clicked-on
        //     popup which we don't want
//         e.layer.bindPopup(popup);
//         popup.setContent(`${e.layer.feature.properties.name}`);
//         e.layer.openPopup();
    });
    MINERAL_SITES_LAYER.on('click', function(e) {
        var prop = e.layer.feature.properties;//e.layer.feature.properties;      
        var msids = maybeArrToStr(prop.mineral_site_ids);
        var ranks = maybeArrToStr(prop.rank);
        var types = maybeArrToStr(prop.type);

        var commdts = getCommodityAndDTsFromSite(prop);
        var conf = prop.top1_deposit_classification_confidence;
        var src = getMineralSiteSourcesTable(prop);
        var exclude_chk = '';
        if (getActiveCMAID()) { // If CMA/modeling tools are active, show 'exclude' checkbox
            // TODO: check prop for checked
            var checked = prop.exclude ? ' checked' : '';
            exclude_chk = `
                <label><span class='label'>Exclude from model training data:</span>
                    <input type='checkbox' id='site_popup_exclude_chk' onchange='toggleExcludeChk("${prop.id}")' ${checked}/>
                </label>`;
        }
        
        e.layer._popup.setContent(`
            <b>${maybeArrToStr(prop.names).join(' /<br>')}</b>
            <br><br>
            <table class='model_parameters_table mineral_site_info_table'>
                <tr>
                    <td class='label'>Commodity:</td>
                    <td class='emri_keyword'>${commdts.commodities.join('</span><span class="emri_keyword_break"> | </span><span class="emri_keyword">')}</td>
                </tr>
                <tr>
                    <td class='label'>Primary deposit type:</td>
                    <td>${prop.top1_deposit_type || '--'}</td>
                </tr>
                    <tr>
                    <td class='label'>Primary deposit group:</td>
                    <td>${prop.top1_deposit_group || '--'}</td>
                </tr>
                <tr>
                    <td class='label'>Primary deposit type conf.:</td>
                    <td> ${conf ? conf.toFixed(2) : '--'}</td>
                </tr>
                <tr><td class='label'>Grade:</td><td>${prop.grade ? prop.grade.toFixed(2) : '--'}</td></tr>
                <tr><td class='label'>Tonnage (Mt):</td><td>${prop.tonnage ? prop.tonnage.toFixed(1) : '--'}</td></tr>
            
            </table>
            <br>
            <span class='label'>Source(s):</span>${src}
    
            <br><br>
            ${exclude_chk} 
        `);
        
        e.layer.openPopup();
    });
   // if ($('#mineral_sites_show_chk').is(':checked')) {
    MINERAL_SITES_LAYER.addTo(MAP);
  //  }
    
    // Update the "display by" selector to include commodity/deposit type
    // candidate filters customized to results
    var all_opts = {commodities: [], dtcs: []};
    $.each(GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites, function(i,site) {
        var commdts = getCommodityAndDTsFromSite(site.properties);
        $.each(all_opts, function(k) {
            $.each(commdts[k], function(c,commdt) {
                if (all_opts[k].indexOf(commdt) == -1) {
                    all_opts[k].push(commdt);
                }
            });
        });
    });
    
    var opts = `
        <option value="site_type" selected>Site type</option>
        <option value="commodity_type">Commodity type</option>
        <option value="top1_deposit_classification_confidence">Primary dep. type conf.</option>
        <option value="tonnage">Tonnage</option>
        <option value="grade">Grade</option>
    `;
    if (getActiveCMAID()) {
        opts += "<option value='exclude'>Included in training</option>";
    }
    
    // ranks
    $.each(['A','B','C','D','E','U'], function(i,d) {
        opts += `<option value='rank__${d}'>Rec. quality: ${d}</option>`;
    });

    // commodities
    $.each(all_opts.commodities.sort(), function(i,d) {
        opts += `<option value='commodity__${d}'>Commodity: ${d}</option>`;
    });
    
    // primary deposit types
    $.each(all_opts.dtcs.sort(), function(i,d) {
        opts += `<option value='deposit_type__${d}'>Prim. deposit type: ${d}</option>`;
    });
    
    // Show the "display by" selector <- only needed if 'display by' dropdown is moved under the KNOWN DEPOSIT SITES filter form
//     $('#mineral_sites_display_by').show();
    
    // Create/add legend
    html = `
        <div class='layer_legend' id='legendcontent_sites'>
            <div class='legend_header'><span class='collapse'>-</span> deposit sites - queried <span class='header_info'>[n=<span style='color:#fff;'>${GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites.length}</span>]</span></div>
            <div class='legend_body'>
                <table>
                    <tr class='buttons'>
                        <td>
                            <div class='topbar_button'>
                                 <span class="link mineral_sites_download_link" onclick="downloadMineralSites('csv');" style="display: inline;">csv</span>|<span class="link mineral_sites_download_link" onclick="downloadMineralSites();" style="display: inline;">shp</span>|<span class="link mineral_sites_download_link" onclick="downloadMineralSites('gpkg');" style="display: inline;">gpkg</span>|<span class="link mineral_sites_download_link" onclick="downloadMineralSites('geojson');" style="display: inline;">geojson</span>|<img title='View tonnage histogram for the sites that have tonnage data' src="/static/cma/img/icons8-histogram-50.png" height="14px" class="download_icon"
                                onclick="createTonnageHistogram();">
                                <img src="/static/cma/img/icons8-scatter-plot-30.png" height="16px" class="download_icon" onclick="createGradeTonnageScatterplot();">
                                <img src="/static/cma/img/icons8-table-48.png" height="16px" class="download_icon" onclick="loadMineralSitesToTable();$('#show_sites').show();">
                                
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <label class='chk_label'>
                                Show on map: <input type='checkbox' onchange='onShowDepositSitesToggle();' id='mineral_sites_show_chk' checked />
                            </label>
                        </td>
                    </tr>
                    <tr>
                        <td class='label'>Display by:</td>
                    </tr><tr>
                        <td><select id='sites_display_select' onchange='onMineralSitesDisplayByChange();'>
                            ${opts}
                        </select></td>
                    </tr>
                </table>
                <div id='sites_legend'></div>
            </div>
        </div>
    `;
    $('#legend_content_sites').html(html);
    
    $('#legendcontent_sites .legend_header').on('click', function(e) {
//         console.log(e);
        e.stopPropagation();
        toggleHeader(e.target);
    });
    
    // Trigger display by change to style the markers
    onMineralSitesDisplayByChange();
    
}

function onShowDepositSitesToggle() {
    var show = $('#mineral_sites_show_chk').is(':checked');
    if (show) {
        MAP.addLayer(MINERAL_SITES_LAYER);
    } else {
        // Remove map layer
        if (MAP.hasLayer(MINERAL_SITES_LAYER)) {
            MAP.removeLayer(MINERAL_SITES_LAYER);
        }
    } 
    
}

function getMineralSiteValsByProperty(prop) {
    var d = [];
    $.each(GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites, function(i,site) {
        var v = site.properties[prop];
        if (v == undefined) {return;} // skip sites w/out data
        d.push(v);
    });
    return d;
}

function getColorBreaksForArray(arr, colormap_template) {
    var tmin = Math.min(...arr);
    var tmax = Math.max(...arr);
    var breaks = colormap_template.map(function(c) {
        return {thresh: tmin + ((tmax-tmin) * c.thresh), color: c.color};
    });
    return breaks
}

function onMineralSitesDisplayByChange() {
    var display_by = $('#sites_display_select').val();
    var display_by_text = $('#sites_display_select option:selected').text();
    
    var fillColor_default = '#999';
    var fillOpacity_default = 0.3;
    
    var fillColor_filterYes = 'orange';
    var fillOpacity_filterYes = 1.0;
    
    var strokeWeight_default = 0.5;
    
    // Map of site_type to style 
    // color map used: https://colorbrewer2.org/#type=qualitative&scheme=Paired&n=6
    site_types = {
        Occurrence: {
            color: '#33a02c',
        },
        Prospect: {
            color: '#b2df8a',
        },
        'Past Producer': {
            color: '#a6cee3',
        },
        Producer: {
            color: '#1f78b4',
        },
        Plant: {
            color: '#e31a1c',
        },
        Unknown: {
            color: '#fb9a99'
        },
        'NotSpecified': {
            color: '#fb9a99'
        }  
    };
    // Commodities
    var commodities = getMineralSiteValsByProperty('commodity');
    commodities.sort();
    var commodity_types = {}
    $.each(commodities, function(i,commodity) {
        commodity_types[commodity] = {color:  d3.schemeCategory20b[i % 20]};
    });
    
    // Map of confidence to style
    var confidence_colormap = [
        {thresh: 0, color: '#fff'},
        {thresh: .1, color: '#f7fcf5'},
        {thresh: .2, color: '#e5f5e0'},
        {thresh: .3, color: '#c7e9c0'},
        {thresh: .4, color: '#a1d99b'},
        {thresh: .5, color: '#74c476'},
        {thresh: .6, color: '#41ab5d'},
        {thresh: .7, color: '#238b45'},
        {thresh: .8, color: '#006d2c'},
        {thresh: .9, color: '#00441b'},
    ];
    
    // Tonnage breaks
    var tonnages = getMineralSiteValsByProperty('tonnage');
    
    // Grade breaks
    var grades = getMineralSiteValsByProperty('grade'); 
    
    var colormaps = {
        top1_deposit_classification_confidence: confidence_colormap,
        tonnage: getColorBreaksForArray(tonnages,confidence_colormap),
        grade: getColorBreaksForArray(grades,confidence_colormap),
    }
    
    MINERAL_SITES_LAYER.eachLayer(function(flayer) {
        prop = flayer.feature.properties;
        var fillColor = fillColor_default;
        var fillOpacity = fillOpacity_default;

        if (display_by == 'site_type') {
            
            // If type is an array, just take the 1st
            var ptype = maybeArrToStr(prop.type)[0];
//             if (ptype.indexOf('[') > -1) {
//                 ptype = JSON.parse(ptype)[0];
//             }
            if (site_types[ptype]) {
                fillColor = site_types[ptype].color;
            } else {
//                 ptype = JSON.parse(prop.type);
//                 fillColor = site_types[ptype].color;
                if (prop.type) {
                    console.log('***new site type!',prop.type);
                }
                fillColor = '#fb9a99';
            }
            flayer.setStyle({
                fillColor: fillColor,
                fillOpacity: 0.9,
                weight: strokeWeight_default,
            });
        } else if (display_by == 'commodity_type') {
            fillColor = commodity_types[prop.commodity].color;
            flayer.setStyle({
                fillColor: fillColor,
                fillOpacity: 0.9,
                weight: strokeWeight_default,
            });
            
        } else if (colormaps[display_by]) {
            var conf = prop[display_by];
            
            if (conf == undefined) {
                fillColor = fillColor_default;
                fillOpacity = 0.1;
                strokeWeight = 0.1;
            } else {
                fillColor = '#fff';
                $.each(colormaps[display_by], function(i,cm) {
                    if (conf >= cm.thresh) {
                        fillColor = cm.color;
                    }
                });
            }
            
            flayer.setStyle({
                fillColor: fillColor,
                fillOpacity: 0.8,
                weight: strokeWeight_default,
            });            
            
        } else {
            var strokeWeight = 0.2;
            var display_cat = display_by.split('__')[0];
            var display_filter = display_by.split('__')[1];
            var commdts = getCommodityAndDTsFromSite(prop);
            
            if (display_by == 'exclude') {
                if (!prop.exclude) {
                    fillColor = fillColor_filterYes;
                    fillOpacity = fillOpacity_filterYes;
                    strokeWeight = 0.5;
                }
            }
            
            if (display_cat == 'commodity') {
                if (commdts.commodities.indexOf(display_filter) > -1) {
                    fillColor = fillColor_filterYes;
                    fillOpacity = fillOpacity_filterYes;
                    strokeWeight = 0.5;
                }
            }
            
            if (display_cat == 'deposit_type') {
                if (commdts.dtcs.indexOf(display_filter) > -1) {
                    fillColor = fillColor_filterYes;
                    fillOpacity = fillOpacity_filterYes;
                    strokeWeight = 0.5;
                }
            }
            if (display_cat == 'rank') {
                if (maybeArrToStr(prop.rank).indexOf(display_filter) > -1) {
                    fillColor = fillColor_filterYes;
                    fillOpacity = fillOpacity_filterYes;
                    strokeWeight = 0.5;
                }
            }
            
//             if (display_cat == 'tonnage') {
//                 if (prop.tonnage) {
//                     fillColor = fillColor_filterYes;
//                     fillOpacity = fillOpacity_filterYes;
//                     strokeWeight = 0.5;
//                 }
//             }
            
            flayer.setStyle({
                weight: strokeWeight,
                fillColor: fillColor,
                fillOpacity: fillOpacity,
//                 opacity: strokeOpacity
            });
            
          
        }
    });
    
    // Create legend
    var lhtml = '';
    if (display_by == 'site_type') {
        $.each(site_types, function(label,obj) {
            lhtml += `<div class='legend_entry'><div class='dot' style='background-color:${obj.color};'></div> ${label}</div>`;
        });
    } else if (display_by == 'commodity_type') {
        $.each(commodity_types, function(label,obj) {
            lhtml += `<div class='legend_entry'><div class='dot' style='background-color:${obj.color};'></div> ${label}</div>`;
        });
    } else if (colormaps[display_by]) {
        var prec = display_by == 'grade' ? 3 : 1;
        lhtml += `<div class='legend_entry'><div class='dot' style='background-color:${fillColor_default};'></div> Undefined</div>`
        $.each(colormaps[display_by], function(i,obj) {
            lhtml += `<div class='legend_entry'><div class='dot' style='background-color:${obj.color};'></div> ${obj.thresh.toFixed(prec)}</div>`;
        });
    } else {
        lhtml = `
            <div class='legend_entry'><div class='dot' style='background-color:${fillColor_filterYes};'></div> ${display_by_text}</div>
            <div class='legend_entry'><div class='dot' style='background-color:${fillColor_default};'></div> other</div>
        `;
    }
    $('#sites_legend').html(lhtml);
}

// Create map control for populating layer legend elements when a layer is 
// selected.
function createLegendControl(element_id,position) {
    position = position || 'topleft';
    
    // Create legend control
    var legendControl = L.Control.extend({
        options: {
            position: position,
        },
        onAdd: function () {
            var c = L.DomUtil.create('div', 'legend');
            
            c.innerHTML = `<div id='${element_id}'></div>`;

            return c;
        }
    });
    MAP.addControl(new legendControl());
}


// Checks that, at minimum, a *commodity* and *extent* is selected in order to
// send the sites query.
function validateLoadSitesButton() {
    var v = $('#commodity').val();
    var ignore_extent = $('#sites_ignoreextent').is(':checked') || !drawnLayer;
    if (v != undefined && (drawnLayer || ignore_extent)) {
        $('#load_sites_button').removeClass('disabled');
        loadMineralSites();
    } else {
        $('#load_sites_button').addClass('disabled');
    }
}

function drawStart(layerType) {
    $('.leaflet-draw-draw-' + layerType)[0].click();
}

// Get the WKT version of the layer on the map that is drawn
// (for sending extent geometries via URL)
function getWKT() {
    
    if (!drawnLayer) { return;}
    
    // Convert the drawn layer to WKT so that it can be sent as a URL parameter
    var gj = drawnLayer.toGeoJSON();
    
    // A loaded-from-file GeoJSON layer may be a FeatureCollection, in which 
    // case we need to unwrap to find the first feature
    var gj = gj.geometry ? gj : gj.features[0];
    
    // Also have to account for potential MultiPolygons; if multi, just grab 
    // the first one
    var coords = gj.geometry.type == 'MultiPolygon' ? 
        gj.geometry.coordinates[0] : 
        gj.geometry.coordinates;
    
    var new_coords = coords[0].map(function(val) {
        return val.map(x => Number(x.toFixed(5)));
    });

    coords = [new_coords];

    var wkt = new Wkt.Wkt();
    wkt.read(JSON.stringify(gj));
    
    // replace spaces w/ + bc can't put spaces in URL
    return wkt.write().replace(/ /g,'+'); 
}

// Returns a stringified number w/ commas added as appropriate
function addCommas(x) {
    if (parseInt(x) >= 1000) {
        x = parseInt(x).toFixed(0);
    }
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Handles clicks on the (i) icon next to 'Select model type' in the MODELING
// section
function showModelInfo(layer_name) {
    var selmod = $('#model_select').val();
    var model = MODELS[$('#model_select').val()];
    
    $('#model_info .parameters_form_title').html(model.name_pretty);
    $('#model_info .content').html(model.description);
    $('#model_info').show();
}

function getActiveCMAID() {
    return $('#cma_loaded').attr('data-cma_id');
    
}

function submitPreprocessAndRun() {
//     alert('Button functionality in progress');
    submitPreprocessing(true);
    
    
    
}

// Send POST request to backend
function submitPreprocessing(process_and_run) {
     var model = MODELS[$('#model_select').val()];

    // TODO: account for if 'ignore extent' is checked; b/c training sites 
    //       submitted for model runs should ALWAYS adhere to extent 

    // Only include training sites IF:
    //    * model is supervised
    //    * label_raster not already in DATACUBE_CONFIG
    var training_sites = [];
    var label_raster_included =  DATACUBE_CONFIG.reduce(function(tot,l) {
        return tot || DATALAYERS_LOOKUP[l.data_source_id].label_raster;
    },false);
    if (!label_raster_included && model.uses_training) {
        if (GET_MINERAL_SITES_RESPONSE_MOST_RECENT && $('#chk_use_sites_queried').is(':checked')) {
            training_sites = GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites.filter(function(s) {
                    return !s.properties.exclude;
            }).map(function(s) {return s.properties.id;});
        }
        if (GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT && $('#chk_use_sites_uploaded').is(':checked')) {
            $.each(GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT.site_coords, function(i,s) {
                training_sites.push(s);
            });
        }
    }
    
    var evidence_layers = DATACUBE_CONFIG.filter(function(l) {
        var d = DATALAYERS_LOOKUP[l.data_source_id];
        return d.gui_model != 'processedlayer';
    });
    
    var cma_id = getActiveCMAID();
    var data = {
        cma_id: cma_id,
        evidence_layers : evidence_layers,
        training_sites: training_sites,
        dry_run: false,
    };
    
    $.ajax(`${URL_PREFIX}submit_preprocessing`, {
        data: JSON.stringify(data),
        type: 'POST',
        dataType: 'json',
        contentType: 'application/json; charset=utf-8',
        success: function(response) {
            console.log(this.url,response);
            var event_id = response.event_id;
            alert(`Pre-processing submitted successfully! Event ID: ${response.event_id}`);
            
            // TODO: Disable the modeling buttons until (a) pre-process is complete
            // or (b) they remove layers? How do I track this?
            
            // Set "processing" td in DATACUBE interface to loading spinner
            $.each(evidence_layers, function(i,l) {
                 $(`tr[data-layername='${l.data_source_id}'] td.processing`).html(
                     "<div class='loading_spinner'></div>"
                );
            });
            
            var expected_layers = evidence_layers.length + (training_sites.length > 0 ? 1 : 0);
            
            // Check for previously processed layers
            var n_processed = 0;
            if (response.previously_processed) {
                n_processed = response.previously_processed.length;
                $('#message_modal_small .content').html(`
                    ${n_processed} layers previously processed for event ID:<br><span class='highlight'>${event_id}</span>
                `);
                $('#message_modal_small').show();
                $.each(response.previously_processed, function(i,lobj) {
                    processNewProcessedLayer(DATALAYERS_LOOKUP[lobj.layer_id]);
                });
            }
            
            
            // Load event ID to status table
            var ts = getDateAsYYYYMMDD(new Date(),true,true).split(' ');
            $('#model_run_status_list').append(`
                <div class='model_run_status_div' data-model_run_id=${event_id}>
                    <div class='model_run_status_header'>
                        Status for pre-processing event ID:
                        <div class='model_run_id'>${event_id}</div>
                    </div>
                    <table class='model_parameters_table model_run_status_table'>
                        <tr>
                            <td class='label'>Submitted at:</td>
                            <td class='timestamp'>
                                <span class='date'>${ts[0]}</span>
                                <span class='time'>${ts[1]}</span>
                            </td>
                        </tr>
                        <tr>
                            <td class='label'>Status:</td>
                            <td class='status'></td>
                        </tr>
                        <tr>
                            <td class='label'>Layers complete:</td>
                            <td><span class='event_n_complete' id='event_n_complete_${event_id}'>${n_processed}</span> of ${expected_layers}
                            </td>
                        </tr>
                        <tr>
                            <td class='label'>Last updated:</td>
                            <td class='last_updated'>
                                <span class='date'>${ts[0]}</span>
                                <span class='time'>${ts[1]}</span>
                            </td>
                        </tr>
                    </table>
                </tr>
            `);
            
            activateRunStatus();
            
             // If all requested layers already processed....
            if (expected_layers == n_processed) {
                $('#model_run_status').removeClass('active');
                showModelingMainPane();
                
                if (process_and_run) {
                    $('#message_modal_small .content').html(`
                        Pre-processing complete; submitting model run.
                    `);
                    $('#message_modal_small').show();
                    submitModelRun();
                }
                return;
            }
            
            // Start monitor for new layers; will stop once the # of submitted 
            // evidence_layers == the # of layers in DATALAYERS_LOOKUP that 
            // match the event_id.
            
            syncProcessedLayers(
                cma_id,
                expected_layers-n_processed,
                response.event_id,
                process_and_run
            );
        },
        error: function(response) {
            console.log(response);
            alert(response.responseText);
        },
    });
}

function activateRunStatus() {
     // Show the 'status' option in the MODELING navigation
    $('#model_run_status').removeClass('active');
    $('#modeling_status_navigation').show();
    showModelRunStatus();
    
}

// Send POST request to backend
function submitModelRun() {
    var model = $('#model_select').val();
    var train_config = {};
    $.each(MODELS_CACHE[model].parameters, function(reqopt,groups) {
        $.each(groups, function(group,parr) {
            $.each(parr, function(i,p) {
                train_config[p.name] = p.value;//p.html_attributes.value;
                
                // Tuples get special processing- represented as string
                // Determines tuple by checking for 'tuple' in the param name
                if (p.name.indexOf('tuple') > -1 && p.value) {
                    train_config[p.name] = p.value.split(',');
                }
            });
        });
    });

    // This is now just a list of ProcessedLayer IDs
    var evidence_layers = []
    $.each(DATACUBE_CONFIG,function(i,l) {
        // Ignore layer if it's an unsupervised model and the layer is a label 
        // raster
//         if (isLabelRasterInDataCube() && !MODELS[model].uses_training) {
//             return;
//         }
        evidence_layers.push(l.data_source_id);
    });
    
    var cma_id = getActiveCMAID();
    var data = {
        cma_id: cma_id,
        model: model,
        train_config: train_config,
        evidence_layers: evidence_layers, //DATACUBE_CONFIG,
//         dry_run: true,
    };
    
    $.ajax(`${URL_PREFIX}submit_model_run`, {
        data: JSON.stringify(data),
        type: 'POST',
        dataType: 'json',
        contentType: 'application/json; charset=utf-8',
        success: function(response) {
            console.log(this.url,response);
            var mrid = response.model_run_id;
            alert(`Model run submitted successfully! Run id: ${mrid}`);
            
            // Load model run ID
            $('#model_run_loaded .model_run_id').html(mrid);
            $('#model_run_loaded').show();
            $('#model_run_edited').hide();
            
            // Load model run to status table
            var ts = getDateAsYYYYMMDD(new Date(),true,true).split(' ');
            $('#model_run_status_list').append(`
                <div class='model_run_status_div' data-model_run_id=${mrid}>
                    <div class='model_run_status_header'>
                        Status for run ID:
                        <div class='model_run_id'>${mrid}</div>
                    </div>
                    <table class='model_parameters_table model_run_status_table'>
                        <tr>
                            <td class='label'>Submitted at:</td>
                            <td class='timestamp'>
                                <span class='date'>${ts[0]}</span>
                                <span class='time'>${ts[1]}</span>
                            </td>
                        </tr>
                        <tr>
                            <td class='label'>Status:</td>
                            <td class='status'>Submitted successfully; in progress...</td>
                        </tr>
                        <tr>
                            <td class='label'>Last updated:</td>
                            <td class='last_updated'>
                                <span class='date'>${ts[0]}</span>
                                <span class='time'>${ts[1]}</span>
                            </td>
                        </tr>
                    </table>
                </tr>
            `);
            
            // Now re-query the CDR so the new model run shows up in the table
            loadModelRuns(cma_id,mrid);
            
            // Toggle data cube if it is open (to clean up UI);
            closeCollapse('.header.datacube');
            
            activateRunStatus();
            
            // Set the MODEL OUTPUTs filter to the provided model_run_id
            // ^^^ don't need this b/c will run after loadModelRuns
//             loadModelOutputs(cma_id,mri);
            
            // Start the model run status monitor
            checkModelRunStatus(mrid);
        },
        error: function(response) {
            console.log(response);
            alert(response.responseText);
        },
    });
}

function closeCollapse(header_sel) {
    if ($(`${header_sel} .collapse`).html() == '-') {
        toggleHeader($(header_sel));
    }
}

function showModelRunStatus() {
    
    $('#modeling_status_pane').show();
    $('#modeling_main_pane').hide();
    $('.mpm_top_options.modeling').hide();
    
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function checkModelRunStatus(model_run_id) {
    
    $.ajax(`${URL_PREFIX}check_model_run_status`, {
        data: {
            model_run_id: model_run_id,
        },
        type: 'GET',
        success: function(response) {
            console.log(this.url,response);
            
            processDataLayersUpdates(response);
            
            // Reload model runs/outputs if udpates
            if (response.DATALAYERS_LOOKUP_UPDATES.length > 0) {
                loadModelRuns(getActiveCMAID(),model_run_id);
                processModelRunsFromCDR(null,model_run_id);
            }
            
            // Update model run status message
            var ts = getDateAsYYYYMMDD(null,true,true).split(' ');
            var sel0 = `.model_run_status_div[data-model_run_id="${model_run_id}"]`;
            $(`${sel0} td.status`).html(response.model_run_status);
            $(`${sel0} td.last_updated`).html(`
                <span class='date'>${ts[0]}</span>
                <span class='time'>${ts[1]}</span>
            `);
            
            // Wait 3 seconds and then check again
            sleep(60000).then(() => {
                checkModelRunStatus(model_run_id);
            });
        },
        error: function(response) {
            console.log(response);
            alert(response.responseText);
        },
    });
}

function showDataLayerInfo(layer_name,model_output,processed_layer) {
    var dl = DATALAYERS_LOOKUP[layer_name];
    var sr = dl.spatial_resolution_m ? addCommas(dl.spatial_resolution_m.toFixed(0)) : '--';
    var attrs = '';
    if (dl.data_format == 'shp') {
        sr = '';
        attrs += `
            <span class='label'>Attributes:</span><br>
            <table class="model_parameters_table vector_attrs">
                <tr>
                    <th>Attribute</td>
                    <th>Values</td>
                </tr>
        `;
        $.each(dl.attribute_stats, function(attr,data) {
            var vals = '';
            if (data.min) {
                vals = `min: <span class='attrvalue'>${data.min.toFixed(3)}</span>, max: <span class='attrvalue'>${data.max.toFixed(3)}</span>`;
            }
            if (data.unique_values) {
                var uvs = data.unique_values;
                uvs.sort();
                vals = `<span title="${JSON.stringify(data.unique_values).replaceAll('"','')}">[`;
                
                if (data.unique_values.length > 3) {
                    vals += `<span class='attrvalue'>${data.unique_values[0]}</span>,...<span class='attrvalue'>${data.unique_values.slice(-1).pop()}</span>]</span>`;
                } else {
                    v0 = '';
                    $.each(data.unique_values, function(i,v) {
                        if (!v) {return;}
                        v0 += `
                            <span class='attrvalue'>${v.replaceAll('<','').replaceAll('>','')}</span>,`;
                    });
                    v0 = v0.slice(0,-1) + ']';
                    vals += v0;
                    
                }
            }
            attrs += `
                <tr>
                    <td>${attr}</td>
                    <td class='vals'>${vals}</td>
                </tr>
            `;
        });
        attrs += '</table>';
        
    } else {
	var smin = dl.stats_minimum == undefined ? '--' : dl.stats_minimum.toFixed(2);
	var smax = dl.stats_maximum == undefined ? '--' : dl.stats_maximum.toFixed(2);
        attrs = `
            <span class='label'>Spatial resolution:</span><br>${sr} m<br><br>
            <span class='label'>Minimum pixel value:</span><br>${smin}<br>
            <span class='label'>Minimum pixel value:</span><br>${smax}<br>
        `
        sr += ' m';
    }
    if (sr) {
        sr = `<span class='label'>Spatial resolution:</span><br>${sr}`;
    }
    var src = `<span class='label'>Original source:</span><br>${dl.authors} ${dl.publication_date}.<br>${dl.reference_url}`;
    
    if (model_output) {
        src = `
            <span class='label'>Model:</span> ${dl.model}<br>
            <span class='label'>Model type:</span> <span id='model_run__type'></span><br>
            <span class='label'>System:</span> ${dl.system} <span class='label'>v</span>${dl.system_version}<br>
            <span class='label'>Model run info:</span> ${dl.model_run_id} (<span class='link' onclick="loadModelRun('${dl.cma_id}','${dl.model_run_id}');">load model run</span>)
        `;
    }
    
    if (processed_layer) {
        var dsid_orig = '';
        if (!dl.label_raster) {
            dsid_orig = `<span class='label'>Original data source ID:</span> <span class='link' onclick="showDataLayerInfo('${dl.data_source_id_orig}');">${dl.data_source_id_orig || '--'}</span><br>`;
        }
        

        src = `
            <span class='label'>PROCESSING INFO:</span><br>
            ${dsid_orig}
            <span class='label'>Label raster?</span> ${dl.label_raster}<br>
            <span class='label'>System:</span> ${dl.system} <span class='label'>v</span>${dl.system_version}<br>
            <span class='label'>Preprocessing event ID:</span> ${dl.event_id}<br>
            <span class='label'>Processing steps:</span><br>
            ${dl.transform_methods}
        `;
        
    }
    
    $('#dl_title').html(dl.name_pretty);
    $('#dl_dsid').html(`<span class='label'>Data source ID:</span><br>${dl.data_source_id}`);
    $('#dl_name').html(`<span class='label'>Evidence layer raster prefix:</span><br>${dl.name}`);
    $('#dl_description').html(`
        <span class='label'>Description:</span><br>
        ${dl.description}
    `);
    $('#dl_data_format').html(`
        <span class='label'>Data format:</span><br>
        ${dl.data_format}
    `);
    $('#dl_attrs').html(attrs);
//     $('#dl_spatial_resolution_m').html(`span class='label'>Download URL:</span><br>${sr}`);
    $('#dl_url').html(`<span class='label'>Download URL:</span><br><a href='${dl.download_url}' target='_blank'>${dl.download_url}</a>`);
    $('#dl_source').html(`${src}`);
    
    if (model_output) {
        getModelRun(dl.model_run_id,dl);
    }
    
    $('#datalayer_info').show();
}


function hideLayer(cmp_id) {
    $(`tr[data-path='${cmp_id}'] td.show_chk input`).prop('checked',false);
    $(`tr[data-path='${cmp_id}'] td.show_chk input`).trigger('change');
    // Do a separate call to remove layer from map
    // - this is needed for cases where the datalayer tr has been removed
    //   already (e.g. if model outputs are cleared) 
    removeLayerFromMap(cmp_id);
    
}


function removeLayerFromMap(layer_name) {
    var layer_name_scrubbed = layer_name.replaceAll('.','').replaceAll(' ','').replaceAll(',','').replaceAll('>','');    
    var datalayer =  DATALAYERS_LOOKUP[layer_name];
    var layer = datalayer.maplayer;
    
    // Remove layer from map
    MAP.removeLayer(layer);

    // Remove legend content
    $(`#legendcontent_${layer_name_scrubbed}`).remove();
}

function onToggleLayerClick(target,layer_name) {
    var chk = $(target);
    var datalayer =  DATALAYERS_LOOKUP[layer_name];
    var layer_name_scrubbed = layer_name.replaceAll('.','').replaceAll(' ','').replaceAll(',','').replaceAll('>','');  
    var layer = datalayer.maplayer;
    
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
        var is_categorical_data = datalayer.description.indexOf('est Matching Un') > -1;
        var vmin = '';
        var vmax = '';
        var svg = '';//VECTOR_LEGENDS[datalayer.vector_format](datalayer.color];
        if (datalayer.data_format == 'tif') {
            var lmin = datalayer.stats_minimum;
            var lmax = datalayer.stats_maximum;
            var precision = 3;//Math.max(-Math.round(Math.log10(lmax-lmin)),1);
            vmin = lmin.toPrecision(precision);
            vmax = lmax.toPrecision(precision);
            //var svg = '';//VECTOR_LEGENDS[datalayer.vector_format](datalayer.color];on(precision);
            svg = `
                <linearGradient id="gradient_${layer_name_scrubbed}">
                    <stop stop-color="#fff" offset="0%" />
                    <stop stop-color="rgb(${datalayer.color})" offset="100%" />
                </linearGradient>
                <rect width="${w}" height="${h}" fill="url(#gradient_${layer_name_scrubbed})" />
            `;
            
            if (datalayer.color == 'diverging') {
                svg = `
                <linearGradient id="gradient_${layer_name_scrubbed}">
                    <stop stop-color="rgb(${COLORS_DIVERGING[0].join(',')})" offset="0%" />
                    <stop stop-color="rgb(${COLORS_DIVERGING[parseInt(COLORS_DIVERGING.length/2)].join(',')})" offset="50%" />
                    <stop stop-color="rgb(${COLORS_DIVERGING[COLORS_DIVERGING.length-1].join(',')}" offset="100%" />
                </linearGradient>
                <rect width="${w}" height="${h}" fill="url(#gradient_${layer_name_scrubbed})" />
            `;
            }
            
        } else {
            svg = VECTOR_LEGENDS[datalayer.vector_format](
                datalayer.color,
                layer_name_scrubbed,
                w,
                h
            );
        }
        
        if (!is_categorical_data) {
            svg = `
                <td>${vmin}</td>
                <td>
                    <div class='colorbar'>
                        <svg height='${h}' width='${w}'>
                            ${svg}
                        </svg>
                    </div>
                </td>
                <td>${vmax}</td>
            `;
            
        } else {
            svg = `<td>[categorical; ${Math.round(vmax+1)} classes]</td>`
            
        }
        html = `
            <div class='layer_legend' id='legendcontent_${layer_name_scrubbed}'>
                ${getLayerNameLabel(datalayer)}
                <div class="close-top layer_legend_close" onclick="hideLayer('${layer_name}')">
                    <img class="close-top-img" height=24 
                        src="/static/cma/img/close-dark.png" 
                        onmouseover="this.src='/static/cma/img/close-light.png'"
                        onmouseout="this.src='/static/cma/img/close-dark.png'">
                </div>
                <table>
                    <tr>
                        ${svg}
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
        $(`#legendcontent_${layer_name_scrubbed}`).remove();
    }
}

// Function for parsing out the data label, linking back to the raw label
// if required
function getLayerNameLabel(dl) {
    var name_pretty = dl.name_pretty;
    
    if (dl.gui_model == 'outputlayer') {
        
        if (dl.name.indexOf('Codebook Map') > -1 ) {
            var pl = DATALAYERS_LOOKUP[dl.name.split(' ').slice(-1)];
            if (pl) {
                name_pretty = `Codebook Map: ${pl.name_pretty}`;
            }
            if (pl && pl.data_source_id_orig) {
                name_pretty = `Codebook Map: ${DATALAYERS_LOOKUP[pl.data_source_id_orig].name_pretty}`;
            }
        } else if (dl.name.length > 60) {
            var pl = DATALAYERS_LOOKUP[dl.name.split('.')[0]];
            if (pl && pl.data_source_id_orig) {
                name_pretty = `${DATALAYERS_LOOKUP[pl.data_source_id_orig].name_pretty}`;
            }
        }
        name_pretty += ` <span class='datalayer_lowlight'>(${dl.system} v${dl.system_version})</span>`;
    }
    if (dl.gui_model == 'processedlayer' && dl.category != 'Training') {
	if (DATALAYERS_LOOKUP[dl.data_source_id_orig]) {
            name_pretty = DATALAYERS_LOOKUP[dl.data_source_id_orig].name_pretty;
	}
	var tms = dl.transform_methods.map(function(tm) {
            var v = tm;
            if (tm.indexOf('impute') > -1) {
                var tmp = JSON.parse(tm.replaceAll("'",'"'));
                v = `impute[${tmp.window_size.join('x')}]`;
            }
            return v;
        }).join('|');
        if (tms) {
            tms  = `|${tms}`;
        }
        name_pretty = `${name_pretty} <span class='datalayer_lowlight'> MPM resample${tms}`;
    }
    return name_pretty
    
}

function checkLabelRasterWithUnsupervised() {
}

function addLayerToDataCube(datalayer) {
    var dsid = datalayer.data_source_id;
    var table_id = '#datacube_layers';
    
    DATACUBE_CONFIG.push({data_source_id: dsid, transform_methods: []});
        
    var psteps = `<td class='processing'><span class='link processingsteps_list' onclick='editProcessingSteps(this);'>[none]</span></td>`
    
    var name_pretty = getLayerNameLabel(datalayer);
    
        
    var ast = '';
    var cls2 = '';
    if (datalayer.gui_model == 'processedlayer') {
        psteps = `<td class='processing complete' onclick="showDataLayerInfo('${dsid}',false,true);">complete &#10003;</td>`;
        
        if (datalayer.label_raster) {
            
            // If there's already a label_raster added, toggle that one out 
            onRemoveDataCubeLayerClick($('tr.cube_layer.label_raster')[0]);
            
            cls2 = ' label_raster';
            if (!MODELS[$('#model_select').val()].uses_training) {
                cls2 += ' disabled';
                toggleLabelRasterEnable(false);
            } else {
                toggleLabelRasterEnable(true);
            }
            ast = '<span class="lr_asterisk">* </span>';
        }   
    }
    
    // Hide instructions 
    $(`${table_id} tr.instructions`).hide();
    
    // Add row 
    var icon_height = 13;
    $(`${table_id} tr.cube_layer:last`).after(`
        <tr class='cube_layer${cls2}' data-layername='${dsid}' data-datacubeindex=${DATACUBE_CONFIG.length-1}>
            <td class='name'>${ast}${name_pretty}</td>
            ${psteps}
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
    
    validateModelButtons();
}

function isLabelRasterInDataCube() {
    return DATACUBE_CONFIG.reduce(function(tot,l) {
        return tot || DATALAYERS_LOOKUP[l.data_source_id].label_raster;
    },false);
}

// Enables/disables model buttons according to selected layers
function validateModelButtons() {
    var model = MODELS[$('#model_select').val()];
    var cma_id = getActiveCMAID();
    var msg = '';
    if (!model || !cma_id) {
        $('#model_button_status').html(msg);
        return;
    }
    
    // Derive conditionals common to both supervised and unsupervised models
    
   //  Check if all layers in cube are processed
    var all_processed = true;
    $.each(DATACUBE_CONFIG, function(i,dl) {
        var l = DATALAYERS_LOOKUP[dl.data_source_id];
        if (l.gui_model != 'processedlayer') {
            all_processed = false;
        }
    });
    // Check if a label raster is needed (i.e. 'supervised' model selected and  
    // NOT in cube)
    var label_raster_included = isLabelRasterInDataCube();
    
    // For supervised models....
    if (model.uses_training) {
        var n_training_sites_selected = Number($('.mineral_sites_n_results.training').html());

        var training_sites_selected = (
            (GET_MINERAL_SITES_RESPONSE_MOST_RECENT &&
            GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites.length > 0) ||
            (GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT &&
            GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT.site_coords.length > 0));
          
        // If no layers in cube and no training sites, disable all buttons
        if (DATACUBE_CONFIG.length == 0 && !training_sites_selected) {
            $('.button.model_process_submit.preprocess').addClass('disabled');
            $('.button.model_process_submit.preprocess_and_run').addClass('disabled');
            $('.button.model_process_submit.run').addClass('disabled');
            
            msg = 'Select at least 1 INPUT LAYER and >0 TRAINING SITES';
            $('#model_button_status').html(msg);
            
            return;
        }
        
        // If the only layer in the cube is the label raster
        if (DATACUBE_CONFIG.length == 1 && label_raster_included) {
            $('.button.model_process_submit.preprocess').addClass('disabled');
            $('.button.model_process_submit.preprocess_and_run').addClass('disabled');
            $('.button.model_process_submit.run').addClass('disabled');
            
            msg = 'Select at least 1 non-training INPUT LAYER';
        }
        
        // Enable ONLY 'pre-process' button IF unprocessed layers exist and 
        // no training data is selected:
        if (!all_processed && !training_sites_selected && !label_raster_included) {
            $('.button.model_process_submit.preprocess').removeClass('disabled');
            $('.button.model_process_submit.preprocess_and_run').addClass('disabled');
            $('.button.model_process_submit.run').addClass('disabled');
            
            msg = 'No training data selected; query or upload training sites or add PROCESSED label raster to enable model RUN buttons';
            
        }
        // Enable ONLY 'pre-process' button IF training sites are selected BUT 
        // no other INPUT LAYERS are selected
        if (training_sites_selected && DATACUBE_CONFIG.length == 0) {
            $('.button.model_process_submit.preprocess').removeClass('disabled');
            $('.button.model_process_submit.preprocess_and_run').addClass('disabled');
            $('.button.model_process_submit.run').addClass('disabled');
            
            msg = 'Select at least 1 non-training INPUT LAYER';
        }
        
        // Disable ONLY 'run' button 
        if (!all_processed || 
            (!label_raster_included && 
              training_sites_selected && 
              DATACUBE_CONFIG.length > 0)
           ) {
            $('.button.model_process_submit.preprocess').removeClass('disabled');
            $('.button.model_process_submit.preprocess_and_run').removeClass('disabled');
            $('.button.model_process_submit.run').addClass('disabled');
        }
        
        // Enable ONLY 'run' if all layers are processed and a label raster is
        // included
        if (all_processed && label_raster_included && DATACUBE_CONFIG.length > 1) {
            $('.button.model_process_submit.preprocess').addClass('disabled');
            $('.button.model_process_submit.preprocess_and_run').addClass('disabled');
            $('.button.model_process_submit.run').removeClass('disabled');
        }
        
  
    } else { // For unsupervised models...
        
        // If no layers in cube, disable all buttons
        if (DATACUBE_CONFIG.length == 0 ||
            (DATACUBE_CONFIG.length == 1 && label_raster_included)) {
            $('.button.model_process_submit.preprocess').addClass('disabled');
            $('.button.model_process_submit.preprocess_and_run').addClass('disabled');
            $('.button.model_process_submit.run').addClass('disabled');
            
            msg = 'Select at least 1 INPUT LAYER';
            $('#model_button_status').html(msg);
            
            return;
        }
        
        // If unprocessed layers in cube, disable RUN  only
        if (!all_processed) {
            $('.button.model_process_submit.preprocess').removeClass('disabled');
            $('.button.model_process_submit.preprocess_and_run').removeClass('disabled');
            $('.button.model_process_submit.run').addClass('disabled');
        } else { // If all processed, enable RUN only
            $('.button.model_process_submit.preprocess').addClass('disabled');
            $('.button.model_process_submit.preprocess_and_run').addClass('disabled');
            $('.button.model_process_submit.run').removeClass('disabled');
        }
    }
    
    $('#model_button_status').html(msg);
}

function onRadioCubeClick(cmp) {
    var el = $(cmp);
    var for_radio = el.prop('for');
    if (!for_radio) {
        return;
    }
    var radio = $(`input[name='${for_radio}']`);
    var valnew = el.prop('class');
    var dsid = for_radio.replace('radiocube_','');
    var datalayer = DATALAYERS_LOOKUP[dsid];
    
    // Update 'checked' property
    radio.prop('checked',false);
    $(`input[name='${for_radio}'][value='${valnew}']`).prop('checked',true);
    
    // Add/remove layer from the datacube layer list
    
    // TODO: check if label raster, if so and another already exists, toggle 
    //       that one out or something. 
    //       Also, updated the TRAINING header info to show the 
    //       #training_info_using_processed_lr span and hide the 
    //       #training_info_using_sites span 
   
    
    // Remove layer from cube
    if (valnew == 'no') {
        // TODO: if/when multiple instances of single data layer are allowed, 
        // this will need to be updated b/c data-layername might not be unique
//         var dcid = $(`#datacube_layers tr[data-layername='${dsid}']`).each(function(el) {
//             var dcid = el.attr('data-datacubeindex');
//             DATACUBE_CONFIG.splice(dcid,1);
//         });
        var splices = [];
        $.each(DATACUBE_CONFIG, function(i,l) {
            if (l.data_source_id == dsid) {
                splices.push(i);
            }
        });
        $.each(splices.reverse(), function(i,s) {
            DATACUBE_CONFIG.splice(s,1);
        });
        
        $(`.datacube_layers_table tr[data-layername='${dsid}']`).remove();
        
        // If label raster was removed, update TRAINING header_info
        if (datalayer.gui_model == 'processedlayer' && datalayer.label_raster) {
            $('#training_info_using_processed_lr').hide();
            $('#training_info_using_sites').show();
            $('#datacube_message_div').html('');
            
            // Un-hide the 'use' sites checkboxes
            $('#chk_use_sites_div').show();
        }
        
        
        // If there are no rows left, show instructions again
        if ($('#datacube_layers tbody tr').length == 1) {
            $('#datacube_layers tr.instructions').show();
        }
    } else { // Add layer to cube
        // If layer is not already in the cube, add it:
        var existing_dsids = DATACUBE_CONFIG.map(function(l) {return l.data_source_id;});
        if (existing_dsids.indexOf(dsid) == -1) {
            addLayerToDataCube(datalayer);
            
             // If added layer is a label raster...
             if (datalayer.gui_model == 'processedlayer' && datalayer.label_raster) {
                 
                // Update TRAINING SITES label
                $('#training_info_using_processed_lr').html(
                    '<span class="lr_asterisk">*</span>selected label raster'
                );
                $('#training_info_using_processed_lr').show();
                $('#training_info_using_sites').hide();
                
                // TODO: Disable the "use" checkboxes?
                // Maybe just hide for now, then ignore when submitting
                $('#chk_use_sites_div').hide();
            }
            
        }
    }
    
    // Update header_info 
    updateDataCubeLabelInfo();
    validateModelButtons();
}

function updateDataCubeLabelInfo() {
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
    var dsid = tr.attr('data-layername');
    var current_dl = DATALAYERS_LOOKUP[dsid];
    
    // Update layername 
    $('#processingsteps_layername').html(
        current_dl.name_pretty
    );
    
    // Update datacube layer index 
    $('#processingsteps_layername').attr(
        'data-datacubeindex',
        tr.attr('data-datacubeindex')
    );
    
    $('#processingsteps_layername').attr(
        'data-data_source_id',
        dsid,
    );
    
    // Empty current table
    $('#processingsteps_listtable tbody').html('');
    populateAddProcessingStep();
     
    // Load any existing processing steps
    $(cmp).find('tr').each(function(i,tr0) {
        var v = $(tr0).find('td').attr('data-value');
        onAddProcessingStep(v,PROCESSING_STEPS[v].name_pretty);
    });

    // Populate tooltip div with recommended processing steps
    var rec_div = $('#recommended_proc_steps');
    rec_div.empty();

    var rec_list = $("<ul></ul>");

    if (current_dl.data_format == 'shp') {
        rec_list.append($(`<li class="rec-warning"><b>Warning</b>: This is a .shp file, applied processing steps may not work as intended.</li>`))
    }
    else {
        // check for the 3 processing step cases
        if (current_dl.stats_hasnans) { // Impute
            rec_list.append($("<li><b>Impute</b>: Datalayer has NaNs</li>"));
        }
        if (current_dl.stats_maximum != 1 && current_dl.stats_minimum != 0) { // Scale
            rec_list.append($(`<li><b>Scale</b>: Datalayer has a minimum of ${current_dl.stats_minimum} and maximum of ${current_dl.stats_maximum}</li>`));
        }
        // Transform suggestions moved to processing step modal in showProcessingStepParameters() function
        // if (current_dl.stats_minimum == 0) { // Transform
        //     rec_list.append($(`<li class="rec-warning"><b>Transform</b>: Datalayer has values less than 0, shouldn't log transform</li>`));
        // } else if (current_dl.stats_minimum < 0) { // Transform
        //     rec_list.append($("<li class='rec-warning'></li>").text(`Transform: Datalayer has values less than 0, shouldn't take log or sqrt transform`));
        // }
    }
    rec_div.append($("<p></p>").text("Recommended processing steps:"))
    rec_div.append(rec_list);
   
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
    console.log(crs_name,crs);
    $('#cma_crs_units').html(crs.units);
    $('#cma_resolution').val(crs.default_resolution);
    getFishnet();
}

function deleteTableRow(cmp) {
    var tr = $(cmp).closest('tr')
    var pstep = tr.attr('data-value');
    var psid = tr.attr('data-index');
    var dcid = $('#processingsteps_layername').attr('data-datacubeindex');
  
    var psobj = PROCESSING_STEPS[pstep];
    
    // Remove entry from DATACUBE_CONFIG
    DATACUBE_CONFIG[dcid].transform_methods.slice(psid,1);
    
    // Remove table row
    tr.remove();
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

    if (
        DATALAYERS_LOOKUP[$('#processingsteps_layername').attr('data-data_source_id')].stats_minimum <= 0 &&
        pstep === "transform"
    ) {
        // Set up onChange event on transform select. Shows warning when log/abs selected and raster min <= 0
        $('#transform__method').on('change', function() {
            $('.parameters_form_warn').empty();
            var selected = $(this).val();
            if (selected === "log" || selected === "sqrt") {
                $('.parameters_form_warn').append($(`<li class='rec-warning'><b>Warning</b>: Datalayer has values less than or equal to 0, shouldn't take ${selected} transform</li>`));
            }
        });
        $('#transform__method').trigger('change');
    } else {
        $('.parameters_form_warn').empty();
    }

    // Now show the modal interface
    $('.overlay.parameters_form').show();
    
}

// Triggers when user clicks 'CONFIGURE MODEL PARAMETERS' in the MODELING
// section
function showModelParameters(el) {

    var tr = $(el).closest('tr')
    var pstep = tr.attr('data-value');
    var psid = tr.attr('data-index');
    var psobj = PROCESSING_STEPS[pstep];
    var model_name = $('#model_select').val();
    
    // Build from cache so that any user modifications are shown
    var model = MODELS_CACHE[model_name];

    // Update form title
    $('.parameters_form_title').html(model.name_pretty.split('(')[0]);
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
//     var layername = $('#processingsteps_layername').html();
    var dcid = $('#processingsteps_layername').attr('data-datacubeindex');
    
    // Index of the processing step
    var psid = $('#processingsteps_listtable tr').length;
    
    var params = '';
    if (DATACUBE_CONFIG[dcid].transform_methods[psid]) {
        $.each(DATACUBE_CONFIG[dcid].transform_methods[psid].parameters, function(p,v) {
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
    
    var dsid = $('#processingsteps_layername').attr('data-data_source_id');
    var dcid = $('#processingsteps_layername').attr('data-datacubeindex');
    
    // Save copy of previous methods to check against new for changes
    var tms_cache = copyJSON(DATACUBE_CONFIG[dcid].transform_methods);
    
    // Reset everything
    DATACUBE_CONFIG[dcid].transform_methods = [];
    
    // Get list of steps from table
    
    var trs = $('#processingsteps_listtable tr');
    var step_html = '[none]'
    if (trs.length > 0) {
        step_html = '<table>';
    }
    trs.each(function(i,tr) {
        var step = $(tr).attr('data-value');
        
        // Get parameters
        params = getParametersFromHTMLattrs(tr);
        
        DATACUBE_CONFIG[dcid].transform_methods.push({name: step, parameters: params});
        step_html += `<tr><td data-value='${step}'>${PROCESSING_STEPS[step].name_pretty}</td></tr>`;
    });
    if (trs.length > 0) {
        step_html += '</table>';
    }
    $(`tr[data-layername='${dsid}'] span.processingsteps_list`).html(step_html);
    
    // Indicate 'edited' if changes were made
    if (!_.isEqual(tms_cache,DATACUBE_CONFIG[dcid].transform_methods)) {
        setModelRunEdited();
    }
}


function updateSHPlabel(shp,el_id,msg) {
    el_id = el_id || 'file_shp';
    msg = msg || 'CHOOSE FILES';
    var c = $(`label[for=${el_id}]`).find('span');
    c.removeClass('selected');
    if (shp) {
        c.html(shp);
        c.addClass('selected');
    } else {
        c.html(msg);
    }
}

function editDistance(s1, s2) {
    s1 = s1.toLowerCase();
    s2 = s2.toLowerCase();

    var costs = new Array();
    for (var i = 0; i <= s1.length; i++) {
        var lastValue = i;
        for (var j = 0; j <= s2.length; j++) {
        if (i == 0)
            costs[j] = j;
        else {
            if (j > 0) {
            var newValue = costs[j - 1];
            if (s1.charAt(i - 1) != s2.charAt(j - 1))
                newValue = Math.min(Math.min(newValue, lastValue),
                costs[j]) + 1;
            costs[j - 1] = lastValue;
            lastValue = newValue;
            }
        }
        }
        if (i > 0)
        costs[s2.length] = lastValue;
    }
    return costs[s2.length];
}

function stringSimilarity(s1, s2) {
    var longer = s1;
    var shorter = s2;
    if (s1.length < s2.length) {
        longer = s2;
        shorter = s1;
    }
    var longerLength = longer.length;
    if (longerLength == 0) {
        return 1.0;
    }
    return (longerLength - editDistance(longer, shorter)) / parseFloat(longerLength);
}

function validateUploadSitesCSV() {
    var fileinput = $('#file_csv');
    var filename = fileinput.val().split('\\').pop();
   
    updateSHPlabel(filename,'file_csv');
    
    if (
            $('#csv_latitude_field').val() &&
            $('#csv_longitude_field').val() && 
            $('#file_csv').get(0).files.length > 0
       ) {
        $('#uploadFormCSV .button.submit').removeClass('disabled');
    } else {
        $('#uploadFormCSV .button.submit').addClass('disabled');
    } 
}

function getCSVcolumnHeaders() {
    var shp, dbf;
    var formData = new FormData($('#uploadFormCSV')[0]);

    validateUploadSitesCSV();
    
    $.each($('#file_csv')[0].files, function(i,file) {
        formData.append('file',file);
    });

    AJAX_UPLOAD_SHAPEFILE = $.ajax(`${URL_PREFIX}get_csv_column_names`, {
        processData: false,
        contentType: false,
        data: formData,
        type: 'POST',
        success: function(response) {
            console.log(this.url,response);
            
            $.each(['longitude','latitude'], function(j,ll) {
                var opts = `<option disabled value='' selected hidden>Select...</option>`;
                var similarities = [];
                $.each(response, function(i,colname) {
                    similarities.push(stringSimilarity(ll,colname));
                    opts += `<option value="${colname}">${colname}</option>`;
                });
                $(`#csv_${ll}_field`).html(opts);
                
                // Set the name with the most similarity to the word 'latitude'
                // to selected
                var most_similar = similarities.indexOf(
                    Math.max.apply(Math,similarities)
                );  
                $(`#csv_${ll}_field`).val(response[most_similar]);
            });
            
            validateUploadSitesCSV();
            
        },
        error: function(response) {
            console.log(response);
        },
    });
};

function loadUserUploadSitesToMap() {
    // Remove current layer if it exists
    if (MAP.hasLayer(MINERAL_SITES_LAYER_USER_UPLOAD)) {
        MAP.removeLayer(MINERAL_SITES_LAYER_USER_UPLOAD);
    }
    
    // Create new layer
    MINERAL_SITES_LAYER_USER_UPLOAD = L.geoJSON(
        GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT.site_coords_gj,{

        pointToLayer: function(feature,latlng) {
            return L.circleMarker(latlng,{
                radius: 5,
                fillColor: '#fff',
                fillOpacity: 0.5,
                opacity: 1,
                color: '#000',
                weight: 0.5,
                className: 'mineral_site_marker',
            });
        },
        onEachFeature: function(feature,layer) {
            var popup = L.popup({
                minWidth: 260,
                autoPan: false,
            });

            layer.bindPopup(popup);
        }
    });
    
    // Create a popup to use in the macrostrat layer
    MINERAL_SITES_LAYER_USER_UPLOAD.on('mouseover', function(e) {
        e.layer.setStyle({radius: 10});
    });
    MINERAL_SITES_LAYER_USER_UPLOAD.on('mouseout', function(e) {
        e.layer.setStyle({radius: 6});
    });
    MINERAL_SITES_LAYER_USER_UPLOAD.on('click', function(e) {
        var exclude_chk = '';
        console.log(e);
        e.layer._popup.setContent(`
            <b>User-uploaded site</b>
            <br><br>
            Coordinates:<br><b>${e.latlng}</b>
            ${exclude_chk} 
        `);
        
        e.layer.openPopup();
    });
    MINERAL_SITES_LAYER_USER_UPLOAD.addTo(MAP);
}
    
    
function onUseSitesChange() {
    updateNsitesLabels();
    
}

function uploadCSV() {
    var shp, dbf;
    var formData = new FormData($('#uploadFormCSV')[0]);

    $.each($('#file_csv')[0].files, function(i,file) {
        formData.append('file',file);
    });
    
    $.each(['latitude','longitude'], function(i,ll) {
        formData.append(`csv_${ll}_field`,$(`#csv_${ll}_field`).val());
    });
    if ($('#csv_filter_by_extent').is(':checked')) {
        var wkt = getWKT();
        if (wkt) {
            formData.append('wkt',getWKT());
        }
    }

    AJAX_UPLOAD_SHAPEFILE = $.ajax(`${URL_PREFIX}upload_sites_csv`, {
        processData: false,
        contentType: false,
        dataType: 'text json',
        data: formData,
        type: 'POST',
        success: function(response) {
            console.log(this.url,response);
            
            GET_MINERAL_SITES_USER_UPLOAD_RESPONSE_MOST_RECENT = response;
            
            // Process the uploaded site points
            loadUserUploadSitesToMap();
                     
            // Show "show user uploaded sites" checkbox in the KNOWN DEPOSIT
            // SITES layer control 
            // ^^^ for now just adding a toggle checkbox in the TRAINING SITES section
            
            // Show "include XX user uploaded sites" and "include XX KNOWN  
            // DEPOSIT SITES checkboxes in the TRAINING section
           
            // Close the upload modal
            $('.overlay.modal_uploadcsv').hide();
            
            // Hide initial instructions 
            $('#user_upload_sites_initial_instructions').hide();
            
            // Update upload file label
            $('#user_upload_sites_file_name').html(
                $('#file_csv')[0].files[0].name
            );
            
            // Show upload sites tools
            $('#user_upload_sites_tools').show();
            
            // TODO: toggle open the DEPOSIT SITES - UPLOADED section
            
            // Upload sites labels
            updateNsitesLabels();
            
        },
        error: function(response) {
            console.log(response);
        },
    });
};
    

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
    var name_ext = 'gpkg';
    
    if (exts.indexOf('shp') > -1) {
        name_ext = 'shp';
    }
    $.each(REQUIRED_SHP_EXTS, function(i,ext) {
        var extspan = $('.modal_uploadshp').find(`span.${ext}`);
        extspan.removeClass('allgood');
        extspan.removeClass('notRelevant');
        if (name_ext != 'shp') {
            extspan.addClass('notRelevant');
        } else {
            if (!exts.includes(ext)) {
                missing_exts.push(ext);
            } else {
                extspan.addClass('allgood');
            }
        }
    });

    if (missing_exts.length == 0) {
        submitButton.removeClass('disabled');
        updateSHPlabel(files_by_ext[name_ext].name);
            
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


function processGetAOIResponse(geojson,onEachFeature) {
//     clearDrawnLayers();
    
    var ds = JSON.parse(JSON.stringify(DRAW_STYLE));
    if (onEachFeature) {
        ds.pointerEvents = 'all';
    }
    var DRAWNLAYER;
    $.each(geojson, function(i,geojson) {
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
    AJAX_GET_FISHNET = $.ajax(`${URL_PREFIX}get_fishnet`, {
        data: {
            resolution: res,
            srid: CRS_OPTIONS[crs].srid.split(':')[1],
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
        msg += "'MPM description' is not set<br>";
    }
    
    // TODO: check for name uniqueness
    
    // Mineral needs to be set 
    if ($('#cma_mineral').val() == '') {
        msg += "'MPM mineral' is not set<br>";
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

function getDateAsYYYYMMDD(dt,hhmm,hhmm_pretty) {
    dt = dt || new Date();
    var dtstr = `${dt.getFullYear()}-${zeroPad(dt.getMonth()+1,2)}-${zeroPad(dt.getDate(),2)}`;
    if (hhmm) {
        var hmstr;
        if (hhmm_pretty) {
            hmstr = ` ${zeroPad(dt.getHours(),2)}:${zeroPad(dt.getMinutes(),2)}`;
        } else {
            hmstr = `_${zeroPad(dt.getHours(),2)}${zeroPad(dt.getMinutes(),2)}`;
        }
        dtstr += hmstr;
    }
    return dtstr;
}

function cleanTimestamp(ts) {
    return `
        <span class='date'>${ts.slice(0,10)}</span>
        <span class='time'>${ts.slice(11,16)}</span>
    `;
}

function showLoadCMAmodal() {   
    $('#load_cma_modal').show();
}

function saveParametersForm() {
    
    var parent_type = $('.parameters_form_title').attr('data-parent_type');
    var parent_id = $('.parameters_form_title').attr('data-parent_id');
    
    var changes = false;
    
    if (parent_type == 'processingstep') {
        // TODO: get layer
//         var layer = $('#processingsteps_layername').html();
//         console.log(parent_id);
        $.each(PROCESSING_STEPS[parent_id].parameters, function(reqopt,groups) {
            $.each(groups, function(group,parr) {
                $.each(parr, function(j,p) {
                    var pname = `#${parent_id}__${p.name}`;
                    var v = $(pname).val();
                    $(`#processingsteps_listtable tr[data-value='${parent_id}']`).attr(
                        `data-param__${p.name}`,
                        $(pname).val()
                    );
                });
            });
        });
    }
    
    if (parent_type == 'model') {
        // Save any values to the model metadata var
        var mobj = MODELS[parent_id];
        var changes = false;
        $.each(mobj.parameters, function(reqopt,groups) {
            $.each(groups, function(g,parr) {
                $.each(parr, function(i,p) {
                    var p_cache = MODELS_CACHE[parent_id].parameters[reqopt][g][i];
                    var v = $(`#${mobj.name}__${p.name}`).val();
                    
                    if (p.input_type == 'range_double') {
                        var vmin = $(`#${mobj.name}__${p.name}__min`).val();
                        var vmax = $(`#${mobj.name}__${p.name}__max`).val();
//                         p.html_attributes.value = [vmin,vmax];
                        v = [vmin,vmax];
                    }
                    
                    p_cache.html_attributes.value = v;
                    
                    // Special case for sri_NN: check for hypertune value
                    //  * if hypertune, set value to null
                    if ($(`input[name="hypertune_${mobj.name}__${p.name}"]:checked`).val() == 'hypertune') {
                        v = null;
                    } 

//                     else {
//             
//                         
//                         if (p.input_type == 'range_double') {
//                             var vmin = $(`#${mobj.name}__${p.name}__min`).val();
//                             var vmax = $(`#${mobj.name}__${p.name}__max`).val();
//     //                         p.html_attributes.value = [vmin,vmax];
//                             v = [vmin,vmax];
// //                             if (v == p_cache.html_attributes.value) {
// //                                 changes = true;
// //                             }
//                         }
//                     }
//                     if (p.input_type != 'range_double' && v != p_cache.value) {
                    if (v != p_cache.value) {
                        changes = true;
                    }
                    p_cache.value = v;
                    


//                     p.html_attributes.value = v;
                    
                    
                });
            });
        });
        
        // If changes were made from a previously loaded model, indicate edited 
        if (changes) {
            setModelRunEdited();
        }
    }
    
    $('.parameters_form').hide();
    
}

function setModelRunEdited() {
    if ($('#model_run_loaded .model_run_id').html() != '[none loaded]') {
        $('#model_run_edited').show();
    }
}

function initiateCMA() {
    data = {};
    $.each(['resolution','mineral','description','crs'], function(i,p) {
        data[p] = $(`#cma_${p}`).val();
    });
    data.resolution = Number(data.resolution);
    data.resolution = [data.resolution,data.resolution];
    data['extent'] = getWKT();
    console.log(data);

    $.ajax(`${URL_PREFIX}initiate_cma`, {
//         processData: false,
//         contentType: false,
        type: 'POST',
        data: data,
        success: function(response) {
            console.log(response);
            
            // If CMA ID not already in the local CMA data store, add
            if (!CMAS_EXISTING[response.cma.cma_id]) {
                CMAS_EXISTING[response.cma.cma_id] = response.cma;
            }
            
            loadCMA(response.cma.cma_id);
        },
        error: function(response) {
            console.log(response);
        }
    });
}

function toggleNationalLayers() {
    if ($('#toggle_national_layers_chk').is(':checked')) {
        
    } else {
        $('#datalayer_container .datalayer_table tr.datalayer_row').show();
    }
}

function toggleIntersectingLayers() {
    // Loop over and toggle each datalayer row
    $('.datalayer_table tr.datalayer_row').each(function () {
        if (drawnLayer && $('#hide_intersecting_cb').is(':checked') && !boundsOverlap($(this).attr('data-path'))) {
            $(this).hide();
        } else {
            $(this).show();
        }
    });
    hideSubcategoryLabels();
}

function hideSubcategoryLabels() {
    // This function will return true if an element has been manually hidden with $(el).hide()
    // and not when an element is hidden because of it's ancestor
    const isExplicitlyHidden = (el) => $(el).css('display') === 'none' || $(el).css('visibility') === 'hidden';

    $('tr.subcategory_label').each(function(idx, subcat_row) {
        var next_rows = [];
        $(subcat_row).nextUntil('tr.subcategory_label').each(function(idxn, next_row) {
            next_rows.push(next_row);
        });
        if (next_rows.every(row => isExplicitlyHidden(row)) || next_rows.length == 0) {
            $(subcat_row).hide();
        }
        else {
            $(subcat_row).show();
        }
    });
}

function boundsOverlap(dl_id) {
    var dl = DATALAYERS_LOOKUP[dl_id]
    var dl_layer = L.geoJSON({
        properties: {},
        geometry: JSON.parse(dl.extent_geom),
        type: 'Feature',
    }, {
        style: {
            color: 'rgb(red)',
            weight: 6,
            opacity: 0.5,
            fillOpacity: 0.00,
            pointerEvents: 'None'
        }
    });

    // This is a hacky? way to check if the returned bounds object is empty
    if (JSON.stringify(dl_layer.getBounds()) === "{}") {
        return true;
    }
    else {
        return drawnLayer.getBounds().overlaps(dl_layer.getBounds());
    }
}

function getLayerControlCategories(dl) {
    var category = dl.category;
    var subcat = dl.subcategory;
    
    if (dl.gui_model == 'outputlayer') {
        category = dl.model;//dl.subcategory;
        subcat = dl.model_run_id;
    }
    if (dl.subcategory == 'User upload') {
        category = 'User upload';
        subcat = dl.category;
    }
    
    return {
        category: category.toUpperCase(),
        subcat: subcat.toUpperCase(),
    }
    
}

function addRowToDataLayersTable(dl) {
    var cats = getLayerControlCategories(dl);
    var category = cats.category;
    var subcat = cats.subcat;
    var category_clean = category.replaceAll(' ','_');
    var table_id = `${dl.gui_model}_table_${category_clean}`;
    var table = $(`#${table_id}`);
    var div = $(`#${dl.gui_model}_container .content.main`);
    
    // Check if the tr already exists and return if so
    if ($(`#${table_id} tr[data-path="${dl.data_source_id}"]`).length > 0) {
        return;
    }
    
    // Add category section if doesn't exist
    if (table.length == 0) {// && dl.gui_model == 'processedlayer') {     
        var category_html = `
            <div class='collapse sub'>
                <div class='header topbar sub ${category_clean}' onclick='toggleHeader(this);'><span class="collapse">+ </span> ${category}</div>
                <div class='content'>
                    <table class='datalayer_table' id='${table_id}'>
                    </table>
                </div> <!--content-->
            </div>  <!--collapse sub-->
        `;
        div.append(category_html);
        table = $(`${table.selector}`);
    }
    
    var subcat = subcat.toUpperCase();
    var name_pretty = getLayerNameLabel(dl);
    var show_chk = `
        <input type='checkbox' 
               onChange='onToggleLayerClick(this,"${dl.data_source_id}");' />
    `;
    var ext = dl.download_url.split('.').slice(-1)[0];
    if (['tif','shp'].indexOf(dl.data_format) == -1) {// != 'tif') {
        show_chk = `${dl.download_url.split('.').slice(-1)[0]}`;
    }
    
    // Add columns headers if date-based subcategory is empty
    var radiocube_header = dl.gui_model == 'outputlayer' ? '' : `Add to cube`;
    if (table.find(`tr.subcategory_label td:contains("${subcat}")`).length == 0) {
        
        table.append(`
            <tr class='subcategory_label'>
                <td>${subcat}</td>
                <td class='colname'>Info</td>
                <td class='colname'>Show</td>
                <td class='colname'>Download</td>
                <td class='colname radiocube'>${radiocube_header}</td>
            </tr>
        `);
    }
    // Add table row
    var radiocube = dl.gui_model == 'outputlayer' ? '' : `
        <div class="radiocube" align="left">
            <input type="radio" name="radiocube_${dl.data_source_id}" value="no" checked>
            <label class='no' for="radiocube_${dl.data_source_id}" onclick="onRadioCubeClick(this);">N</label>
            <input type="radio" name="radiocube_${dl.data_source_id}" value="yes" >
            <label class='yes' for="radiocube_${dl.data_source_id}" onclick="onRadioCubeClick(this);">Y</label>
        </div>
    `;
    table.append(`
        <tr class='datalayer_row' data-path="${dl.data_source_id}" onmouseover='showLayerExtentPreview("${dl.data_source_id}");' onmouseout='hideLayerExtentPreview();'>
            <td class='name' title='${dl.name}'>${name_pretty}</td>
            <td class='info' onclick='showDataLayerInfo("${dl.data_source_id}",${dl.gui_model == 'outputlayer'},${dl.gui_model == 'processedlayer'});'><img src="/static/cma/img/information.png" height="16px" class="download_icon"></td>
            <td class='show_chk'>${show_chk}</td>
            <td class='download'>
                <a href='${dl.download_url}' target='_blank'>${dl.data_format}</a>
            </td>
            <td>${radiocube}</td>
        </tr>
    `);
    
    if ($('#datacube_layers').is(':visible')) {
        $('.radiocube').show();
    }
    
}


function showLayerExtentPreview(dsid) {
    var dl = DATALAYERS_LOOKUP[dsid];
    var extent_geom = dl.extent_geom;
    
    // Remove existing drawings before starting new one
    if (extentPreviewLayer && MAP.hasLayer(extentPreviewLayer)) {
        MAP.removeLayer(extentPreviewLayer);
    }
    
    extentPreviewLayer = L.geoJSON({
            properties: {},
            geometry: JSON.parse(extent_geom),
            type: 'Feature',
        }, {
            style: {
                color: `rgb(${dl.color})`,
                weight: 6,
                opacity: 0.5,
                fillOpacity: 0.00,
                pointerEvents: 'None'
            }
        }
    );

    MAP.addLayer(extentPreviewLayer);
}


function hideLayerExtentPreview() {
     // Remove existing drawings before starting new one
    if (extentPreviewLayer && MAP.hasLayer(extentPreviewLayer)) {
        MAP.removeLayer(extentPreviewLayer);
    }
}
    
    
function uploadDataLayer() {
    var formData = new FormData();
    $('#uploadForm_datalayer input').each(function(i,input) {
        var id = input.id;
        if (id.indexOf('uploaddl') > -1) {
            id = id.split('__')[1];
            formData.append(id, $(input).val());
        }
    });
    $('#uploadForm_datalayer select').each(function(i,input) {
        var id = input.id;
        if (id.indexOf('uploaddl') > -1) {
            id = id.split('__')[1];
            formData.append(id, $(input).val());
        }
    });

    formData.append('file',$('#file_datalayer')[0].files[0]);

//     $('.modal_uploaddatalayer').hide();
    if (AJAX_UPLOAD_SHAPEFILE) {
        AJAX_UPLOAD_SHAPEFILE.abort();
    }
    setLoadingButton('submit_upload_datalayer_button');
//     AUDIO.submit.play();
    AJAX_UPLOAD_SHAPEFILE = $.ajax(`${URL_PREFIX}upload_datalayer`, {
        processData: false,
        contentType: false,
        data: formData,
        type: 'POST',
        success: function(response) {
            console.log(this.url,response);
            
            var dl = response.datalayer;
            
            // Create WMS map layer so it can be loaded to map
            createMapLayer(dl.data_source_id,dl)
            
            // Add layer lookup 
            DATALAYERS_LOOKUP[dl.data_source_id] = dl;
            
            // Add the layer to the layer list
//             var table = $('#user_upload_layers_table');
            addRowToDataLayersTable(dl);
            
            // Reset upload form
            updateSHPlabel(
                null,
                'file_datalayer',
                'CHOOSE TIF'
            );
            $('.modal_uploaddatalayer').hide();
// 
            var e = $('#file_datalayer');
            e.wrap('<form>').closest('form').get(0).reset();
            e.unwrap();
            
            resetButton('submit_upload_datalayer_button','Submit');
            
        },
        error: function(response) {
            console.log(response);
//             AUDIO.error.play();
            resetButton('submit_upload_datalayer_button','Submit');
            alert(response.responseText);
        },
    });
}
    
function startNewModelRun(are_you_sure) {
    $('.model_run_are_you_sure').hide();
    $('.mpm_top_options.modeling').show();
    
    // If things have changed, make sure user has a chance to cancel first
    if (are_you_sure && $('#model_select').val()) {
        $('.overlay.model_run_are_you_sure').show();
    } else {
        resetModelUI(true);
        $('#modeling_initial_message2').hide();
        $('.model_select_div').show();
    }
}

function onStartedCMA(cma) {
//     var cma_description = $('#cma_description').val();
    $('#cma_loaded').attr('data-cma_id',cma.cma_id);
    $('#cma_loaded').html(cma.description);
    $('#cma_loaded').attr('data-cma_id', );
    $('#cma_loaded').removeClass('notactive');
    showCMAstart();
    
    $('#modeling_initial_message').hide();
    $('#modeling_initial_message2').show();
    
    $('.model_select_div').hide();
    
    // Hide "Choose existing MPM" modal
    $('#load_cma_modal').hide();
    
    // Reset model UI
    resetModelUI(true);
}


function createGradeTonnageScatterplot() {
    var elid = '#graph_modal_content';
    $(elid).empty();
    
    var data = [];
    $.each(GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites, function(i,site) {
        var tonnage = site.properties.tonnage;
        var grade = site.properties.grade;
        if (!tonnage || !grade) {return;} // skip sites w/out tonnage data
        data.push({tonnage: tonnage, grade: grade});
    });
    
    // set the dimensions and margins of the graph
    var margin = {top: 10, right: 30, bottom: 50, left: 60},
        width = 460 - margin.left - margin.right,
        height = 400 - margin.top - margin.bottom;

    // append the svg object to the body of the page
    var svg = d3.select(elid)
    .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
    .append("g")
        .attr(
            "transform",
            `translate(${margin.left},${margin.top})`);
        
    // Y axis: scale and draw:
    var y = d3.scaleLinear()
        .domain([
            d3.min(data, function(d) { return +d.grade }),
            d3.max(data, function(d) { return +d.grade})
        ])
        .range([height, 0]);
        
    svg.append("g")
        .call(d3.axisLeft(y));
    
    // X axis: scale and draw:
    var x = d3.scaleLinear()
        .range([0, width]);
    x.domain([0, d3.max(data, function(d) { return +d.tonnage})]);   
        
    svg.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x));

    // append the points
    svg.append('g')
        .selectAll('dot')
        .data(data)
        .enter()
        .append('circle')
            .attr('cx', function(d) { return x(d.tonnage);})
            .attr('cy', function(d) { return y(d.grade);})
            .attr('r', 6)
            .style('fill','#69b3a2');
   
    
    // x-axis label
    svg.append('text')
        .style('fill', '#999')
        .attr('text-anchor','middle')
        .attr('class','camera_header')
        .attr('transform', `translate(${width/2},${height+40}) `)
        .text('million tonnes');
        
    // y-axis label
    svg.append('text')
        .style('fill', '#999')
        .attr('text-anchor','middle')
        .attr('class','camera_header')
        .attr('transform', `translate(-40,${height/2}) rotate(-90)`)
        .text('grade (%)');
        
        
    $('#graph_modal_header').html('Grade/tonnage');
    $('#graph_modal').show();
        
}

function createTonnageHistogram() {
    var elid = '#graph_modal_content';
    $(elid).empty();
    
    var data = [];
    $.each(GET_MINERAL_SITES_RESPONSE_MOST_RECENT.mineral_sites, function(i,site) {
        var tonnage = site.properties.tonnage;
        if (!tonnage) {return;} // skip sites w/out tonnage data
        data.push({tonnage: tonnage});
    });
    
    // set the dimensions and margins of the graph
    var margin = {top: 10, right: 30, bottom: 50, left: 40},
        width = 460 - margin.left - margin.right,
        height = 400 - margin.top - margin.bottom;

    // append the svg object to the body of the page
    var svg = d3.select(elid)
    .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
    .append("g")
        .attr(
            "transform",
            `translate(${margin.left},${margin.top})`);
        
    // X axis: scale and draw:
    var x = d3.scaleLinear()
        .domain([
            d3.min(data, function(d) { return +d.tonnage }),
            d3.max(data, function(d) { return +d.tonnage})
        ])
        .range([0, width]);
    svg.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x));

    // set the parameters for the histogram
    var histogram = d3.histogram()
        .value(function(d) { return d.tonnage; })   // I need to give the vector of value
        .domain(x.domain())  // then the domain of the graphic
        .thresholds(x.ticks(10)); // then the numbers of bins

    // And apply this function to data to get the bins
    var bins = histogram(data);
    
    // Y axis: scale and draw:
    var y = d3.scaleLinear()
        .range([height, 0]);
        y.domain([0, d3.max(bins, function(d) { return d.length; })]);   // d3.hist has to be called before the Y axis obviously
    svg.append("g")
        .call(d3.axisLeft(y));

    // append the bar rectangles to the svg element
    svg.selectAll("rect")
        .data(bins)
        .enter()
        .append("rect")
            .attr("x", 1)
            .attr("transform", function(d) { return `translate(${x(d.x0)},${y(d.length)})`; })
            .attr("width", function(d) { return x(d.x1) - x(d.x0) -1 ; })
            .attr("height", function(d) { return height - y(d.length); })
            .style("fill", "#69b3a2")
    
    // x-axis label
    svg.append('text')
        .style('fill', '#999')
        .attr('text-anchor','middle')
//             .attr('dy',30)
        .attr('class','camera_header')
        .attr('transform', `translate(${width/2},${height+40})`)
        .text('million tonnes');
        
        
    $('#graph_modal_header').html('Site tonnage histogram');
    $('#graph_modal').show();
        
    
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
    AJAX_UPLOAD_SHAPEFILE = $.ajax(`${URL_PREFIX}get_vectorfile_as_geojson`, {
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
            drawnLayer = processGetAOIResponse(response.geojson);
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
    AJAX_UPLOAD_SHAPEFILE = $.ajax(`${URL_PREFIX}get_geojson_from_file`, {
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
            drawnLayer = processGetAOIResponse(response.geojson);
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
