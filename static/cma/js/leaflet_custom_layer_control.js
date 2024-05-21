// Initialize map
MAP = L.map('map', {
    zoomControl: false // disable the +/-
    }
).setView([33, -95], 4);


// Set up basemap options
var Esri_WorldImagery = L.tileLayer(
    'http://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri,Source: Esri/i-cubed/USDA/USGS/AEX/GeoEye/Getmapping/Aerogrid/IGN/IGP/UPR-EGP/GISUserCommunity'
});

var Esri_WorldGrayCanvas = L.tileLayer(
    'http://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
        maxZoom: 16
});

var OpenStreetMap_Mapnik = L.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '' //'&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
});

var CartoDB_DarkMatter = L.tileLayer(
    'http://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="http://cartodb.com/attributions">CartoDB</a>',
        subdomains: 'abcd',
        maxZoom: 19,
        opacity: 1.0
});

var basemap_options = {
    'OSM Mapnik': OpenStreetMap_Mapnik,
    'ESRI Gray' : Esri_WorldGrayCanvas,
    'ESRI Aerial': Esri_WorldImagery,
    'CartoDB Dark': CartoDB_DarkMatter
}
OpenStreetMap_Mapnik.addTo(MAP);


////////////////////////////////////////////////////////////////////////////////
// Legend control

function checkRadioByRow(cmp) {
    if (cmp.nodeName == 'TD') {
        if (cmp.nextElementSibling) {
            cmp.nextElementSibling.firstElementChild.checked = true;
        }
        if (cmp.firstElementChild) {
            cmp.firstElementChild.checked = true;
        }
    }
}

////////////////////////////////////////////////////////////////////////////////
// Custom basemap selector

function selectBasemap(cmp,name) {

    if (cmp.nodeName == 'TD') {
        cmp.nextElementSibling.firstElementChild.checked = true;        
    }
    
    $.each(basemap_options, function(b, basemap) {
        MAP.removeLayer(basemap);
    });
//     basemap_options[e.value].setZindex = -1;
    MAP.addLayer(basemap_options[name],true);

}


////////////////////////////////////////////////////////////////////////////////
// Custom "other WMS data" selector

function onToggleOtherLayerClick(target, id) {
    target = $(target);
    var chk;
    var is_label = false;
    var id = id || target.prop('id').split('-')[0];
    
    
    // ID the associated checkbox
    if (target.prop('nodeName') == 'INPUT') {
        chk = $(target);
    } else if (['SPAN','DIV','TD'].indexOf(target.prop('nodeName')) > -1) {
        chk = $(`[id="${id}-checkbox"]`);
        is_label = true;
    }

    // Handle a click on the label 
//     console.log(chk,chk[0]);
    if (is_label && !chk[0].checked) {
        chk.prop('checked', true);
    } else if (is_label && chk[0].checked) {
        chk.prop('checked', false);
    }

    var checked_checkboxes = $('td.control_input input[type="checkbox"]:checked'
        ).map(function(i,v) { return v.id.replace('-checkbox','');});
    if (images[id] && images[id].as_checkbox) {
        if (images[id].layers) {
            $.each(images[id].layers, function(l,layer) {
                MAP.removeLayer(layer);
            });
        }
        $(`[id="${id}-legend"]`).slideUp(50);
    } else {
        var tmp_s = new Date();
        
        $.each(images, function(iid, obj) {
            if (obj.layers) {
                $.each(obj.layers, function(l,layer) {
                    MAP.removeLayer(layer);
                });
                
//                 if (obj.as_checkbox) {
//                     if ($(`#${iid}-checkbox`)[0].checked) {
//                         checked_checkboxes.push(iid);
//                     }
//                 }
//                 $(`#${iid}-legend`).slideUp(50);
            }
        });
    }
//     // Remove all other checkboxes b/c we want them treated as radios
//     if (images[id].as_checkbox) {
//         $.each(images, function(iid, obj) {
//             if (obj.as_checkbox) {
//                 $.each(obj.layers, function(l,layer) {
//                     map.removeLayer(layer);
//                 });
//                 $(`#${iid}-legend`).slideUp(50);
//             }
//         });
//     }
        
        
    var tmp_s3 = new Date();
    // Add selected layer
    if (chk[0].checked && images[id]) {
        $.each(images[id].layers, function(l,layer) {
            MAP.addLayer(layer);
        });
        $(`[id="${id}-legend"]`).slideDown(50);
    
        // Update map label
        loadImageryDateLabel(id);
    } else if (images[id] && !images[id].as_checkbox) {
        // Select the 'imagery oFF label'
        $('#off-checkbox').prop('checked',true);
    }
    
    // Add any checked checkbox layers back on top
    $.each(checked_checkboxes, function(c, chk) {
        $.each(images[chk].layers, function(l,layer) {
//             console.log('adding layer...', layer);
//             map.removeLayer(layer);
            MAP.addLayer(layer);
        });
        $(`#${chk}-legend`).slideDown(0);
        
    });
}


function loadImageryDateLabel(id) {
    var tmp = images[id].label.split('_')[0];
    var dtstr = tmp.substring(0,4) + '-' + tmp.substring(4,6) + '-' + tmp.substring(6,8);
    dtstr = String(new Date(dtstr + ' 12:00'));
    $('#map-imagery-date').html(dtstr.replace('000','').split(' 12:00')[0]);
}

$('.header').hover(
    function() {
        $(this).find('td.collapse').css('font-weight',900);
    },
    function() {
        $(this).find('td.collapse').css('font-weight',500);
        
    }
);

function toggleHeader(hdr) {
    var do_hide = false;
    $(hdr).find('td.collapse').text(function(_, value){
        do_hide = value == '-';
        return value=='-'?'+':'-'
    });
    $(hdr).find('span.collapse').text(function(_, value){
        return value=='-'?'+':'-'
    });
//     var filter = do_hide ? 'tr[style*="display:table-row"]' : 'tr[style*="display:none"]';
    var filter = '';
    $(hdr).nextUntil('tr.divider', filter).slideToggle(100, function(){});    
};

function toggleLayerHeader(hdr) {
//     var do_hide = false;
    $(hdr).find('td.collapse').text(function(_, value){
//         do_hide = value == '-';
        return value=='-'?'+':'-'
    });
    $(hdr).find('span.collapse').text(function(_, value){
        return value=='-'?'+':'-'
    });
//     var filter = do_hide ? 'tr[style*="display:table-row"]' : 'tr[style*="display:none"]';
    var filter = '';
    
//     $.fn.report = function(c) {
//         console.log(c);
//     }
//     if ($(hdr).attr('id').indexOf('Background') > -1) {
    $(hdr).nextUntil('tr.divider').slideToggle(10, function(){});
//     } else {
//         $(hdr).next('tr.m-basemap-selector-group').find('.group-div').slideToggle(200);
//     }
//     $(hdr).next('tr.m-basemap-selector-group').find('div.group-div').slideToggle(200, function(){});


    
};

function toggleYear(hdr) {
   $(hdr).find('td.collapse').text(function(_, value){
       return value=='-'?'+':'-'
    });
    $(hdr).find('span.collapse').text(function(_, value){
       return value=='-'?'+':'-'
    });
   
//     $(hdr).find('.m-basemap-selector-group').slideToggle(200, function(){});
    $(hdr).nextUntil('tr.m-basemap-year-divider').slideToggle(10, function(){});
//     $(hdr).nextUntil('tr.divider').slideToggle(10, function(){});
    
};


////////////////////////////////////////////////////////////////////////////////
// Custom Layer Control
// .. this is awful, but I couldn't figure out an easy way to just extend
// the original L.Control.Layers object
var CustomLayerControl = L.Control.extend({
    // @section
    // @aka Control.Layers options
    options: {
        // @option collapsed: Boolean = true
        collapsed: true,
        organize_imagery: false,
        position: 'bottomright',
        sortLayers: true,
        sortFunction: function(aLayer,bLayer,a,b){

            if (a.length > 4 && b.length > 4) {
                return a.localeCompare(b);
            }
            return Number(String(b).substr(-4)) - Number(String(a).substr(-4));
            
        }
    },

    initialize: function (baseLayers, overlays, groups, options) {
        L.setOptions(this, options);
        this._groups = groups;
        this._layers = [];
        this._lastZIndex = 0;
        this._handlingClick = false;
        this._baseLayers = baseLayers;
        
        
//         for (var i in baseLayers) {
//             if (baseLayers[i].layers && i < 0) {
//                 this._addLayer(baseLayers[i].layers[0], i);
//             }
//         }

//         for (i in overlays) {
//             this._addLayer(overlays[i], i, true);
//         }
    },

    onAdd: function (map) {
        this._initLayout();
        this._update();

        this._map = map;
        MAP.on('zoomend', this._checkDisabledLayers, this);

        return this._container;
    },

    onRemove: function () {
        this._map.off('zoomend', this._checkDisabledLayers, this);

        for (var i = 0; i < this._layers.length; i++) {
                this._layers[i].layer.off('add remove', this._onLayerChange, this);
        }
    },

    // @method addBaseLayer(layer: Layer, name: String): this
    // Adds a base layer (radio button entry) with the given name to the control.
    addBaseLayer: function (layer, name) {
        this._addLayer(layer, name);
        return (this._map) ? this._update() : this;
    },

    // @method addOverlay(layer: Layer, name: String): this
    // Adds an overlay (checkbox entry) with the given name to the control.
    addOverlay: function (layer, name) {
        this._addLayer(layer, name, true);
        return (this._map) ? this._update() : this;
    },

    // @method removeLayer(layer: Layer): this
    // Remove the given layer from the control.
    removeLayer: function (layer) {
        layer.off('add remove', this._onLayerChange, this);

        var obj = this._getLayer(L.stamp(layer));
        if (obj) {
                this._layers.splice(this._layers.indexOf(obj), 1);
        }
        return (this._map) ? this._update() : this;
    },

    // @method expand(): this
    // Expand the control container if collapsed.
    expand: function () {
        L.DomUtil.addClass(this._container, 'leaflet-control-layers-expanded');
        this._form.style.height = null;
        var acceptableHeight = this._map.getSize().y - (this._container.offsetTop + 50);
        if (acceptableHeight < this._form.clientHeight) {
                L.DomUtil.addClass(this._form, 'leaflet-control-layers-scrollbar');
                this._form.style.height = acceptableHeight + 'px';
        } else {
                L.DomUtil.removeClass(this._form, 'leaflet-control-layers-scrollbar');
        }
        this._checkDisabledLayers();
        return this;
    },

    // @method collapse(): this
    // Collapse the control container if expanded.
    collapse: function () {
//         L.DomUtil.removeClass(this._container, 'leaflet-control-layers-expanded');
        return this;
    },

    _initLayout: function () {
        var className = 'leaflet-control-layers',
            container = this._container = L.DomUtil.create('div', className);

        // makes this work on IE touch devices by stopping it from firing a mouseout event when the touch is released
        container.setAttribute('aria-haspopup', true);

        L.DomEvent.disableClickPropagation(container);
        if (!L.Browser.touch) {
                L.DomEvent.disableScrollPropagation(container);
        }

        var form = this._form = L.DomUtil.create('form', className + '-list');

        if (!L.Browser.android && this.options.collapse) {
                L.DomEvent.on(container, {
                        mouseenter: this.expand,
                        mouseleave: this.collapse
                }, this);
        }

        var link = this._layersLink = L.DomUtil.create(
            'a', className + '-toggle', container
        );
        link.href = '#';
        link.title = 'Layers';

        if (L.Browser.touch) {
                L.DomEvent
                    .on(link, 'click', L.DomEvent.stop)
                    .on(link, 'click', this.expand, this);
        } else {
                L.DomEvent.on(link, 'focus', this.expand, this);
        }

        // work around for Firefox Android issue https://github.com/Leaflet/Leaflet/issues/2033
//         L.DomEvent.on(form, 'click', function () {
//             setTimeout(L.bind(this._onInputClick, this), 0);
//         }, this);

        this._map.on('click', this.collapse, this);

        if (!this.options.collapsed) {
                this.expand();
        }
//         this._separator = L.DomUtil.create('div', className + '-separator', form);
        
        // CUSTOMIZATION BEGINS
        
        this._layersTableDiv = L.DomUtil.create('div', 'customLayersTableDiv', form);
        this._layersTable = L.DomUtil.create('table', 'customLayersTable', this._layersTableDiv);
        

        var header_colspan = 1;
        if (this.options.organize_imagery) {
            header_colspan = 3;
        }
        //////////////////////////////////////////////////////////////
        // Other layers
        
        function addBuffer() {
            var buff = L.DomUtil.create(
                        'tr', 'm-basemap-selector buffer', mom._layersTable);
            buff.innerHTML = `<td colspan=${header_colspan+1}></td>`;
        }
        
        var mom = this;
        mom._layerGroups = {};
        var currGroup;
        var keys = Object.keys(mom._baseLayers);
        keys.sort();
        var currYear;
        var firstYear = true;
        var delay_legend;
        var delay_legend_id;
        $.each(keys, function(i,id) {
            var group = mom._baseLayers[id].group;
            var type = 'checkbox';
            var name = 'imagery';
            if (group == 'other') {
                return;
            }
            if (group != currGroup) {
                L.DomUtil.create(
                    'tr', 'm-basemap-selector divider', mom._layersTable);
                
                mom._otherHeader = L.DomUtil.create(
                    'tr', 'm-basemap-selector header', mom._layersTable);
                
                mom._otherHeader.innerHTML= `
                    <td colspan=${header_colspan}>${group}</td>
                    <td class="collapse">-</td>`;

                mom._otherHeader.id = group.replace(/ /g,'') + '-header';
                
                // For each group, set up this structure:
                //  <tr>
                //      <td colspan=[3]>
                //          <div class='group-div'>
                //              <table class='customLayersTable'>
                mom._layerGroups[group] = {};
                mom._layerGroups[group].tr = L.DomUtil.create(
                    'tr','m-basemap-selector-group', mom._layersTable);
                mom._layerGroups[group].tr_td = L.DomUtil.create(
                    'td',null, mom._layerGroups[group].tr);
                $(mom._layerGroups[group].tr_td).attr('colspan',header_colspan+1);
                mom._layerGroups[group].div = L.DomUtil.create(
                    'div','group-div', mom._layerGroups[group].tr_td);
                mom._layerGroups[group].table = L.DomUtil.create(
                    'table','customLayersTable', mom._layerGroups[group].div);
                mom._layerGroups[group].rows = {};
                mom._otherLegends = {};
                currGroup = group;
                currYear = undefined;
                firstYear = true;
            }
            
            var attr = mom._baseLayers[id];
            var onclick = `onClick="onToggleOtherLayerClick(this,'${id}')"`;
            if (mom.options.organize_imagery && 
                (group.indexOf('imagery') > -1 ||
                 ['hydrodynamic vids','beach mon reports'].indexOf(group) > -1)) {
                // if imagery, group by dates
                
                var ldate = attr.label.split('_')[0].replace('000','');
                var ldateYear = ldate.substring(0,4);
                var ldate = delay_legend ? 
                    '' : ldate.substring(4,6) + '-' + ldate.substring(6,8);
                var lsource = attr.label.split('_')[1].replace('zzz','');
                var lsource_short = imagery_sources[lsource];
                var lproduct = attr.label.split('_')[2];
                var legend = attr.legend || delay_legend;
                var lid = delay_legend_id || id;
                var lab = lsource; // data label
                if (lab == 'SkySat') {
                    lab = `<span style='color:#cfdbe2;'>${lab}</span>`;
                }
                if (lab == 'DigitalGlobe') {
                    lab = `<span style='color:#a4f4cc;'>${lab}</span>`;
                }
                
                // Interpreted imagery is a special case; we want to display
                // the classified image, the original image, AND any RSRF polygons
                // This means holding off on inserting the legend until after
                // the next layer is added, and applying special labeling to
                // indicate the product instead of the source
                if (group == 'interpreted imagery') {
                    lab = attr.legend ? lproduct : `${lab} image`;
                    
                    // If it has a legend, it's the classified image
                    // (as opposed to the original image)
                    if (attr.as_checkbox) {
                        onclick = `onClick="onToggleOtherLayerClick(this,'${id}', true)"`;
                        type = 'checkbox';
  
                        // If there's no legend, assume it's the RSRF layer
                        var has_rsrf;
                        if (!attr.legend) { 
                            name = 'rsrf_polygons';
                            lab = `${lproduct} polygons`;
                            has_rsrf = true;
                            
                        } else {
                            // otherwise assume it's the classification layer
                            lab = lproduct;
                            name = 'classifications';
                            if (lab.indexOf('HeatMap') == -1) {
                                delay_legend = attr.legend;
                                delay_legend_id = id;
                            legend = null;
                            }
                            if (has_rsrf) {
                                // If there's an RSRF layer, the date will go
                                // with that one
                                ldate = '';
                                has_rsrf = false;
                            }
                        }
                    }
                }
       
                // If new year, add label div
                if (currYear != ldateYear) {
                    currYear = ldateYear;
                    var cls = firstYear ? ' firstyear': '';
                    mom._layerGroups[group].rows[ldateYear] = L.DomUtil.create(
                        'tr', 'm-basemap-year-divider' + cls, mom._layerGroups[group].table
                    );
                    mom._layerGroups[group].rows[ldateYear].innerHTML = `
                        <td class="year_label" colspan=${header_colspan}>
                            ${currYear}
                        </td>
                        <td class="collapse">-</td>`;
                    
                    firstYear = false;
                }
                
                if (['drone imagery','hydrodynamic vids','beach mon reports'].indexOf(group) > -1
                    && attr.vidlink) {
//                     console.log(group);
                    var vlink = attr.vidlink;
                    var n = attr.label.split('_')[3];
                    var vid = `vid${n}`;
                    var is_hydro = group == 'hydrodynamic vids'
                    var onclick = `onclick="showEmbeddedVideo('${vlink}',${is_hydro})"`;
                    mom._layerGroups[group].rows[vid] = L.DomUtil.create(
                        'tr', 'm-basemap-selector', mom._layerGroups[group].table);
                    
                    if (group == 'drone imagery') {
                        mom._layerGroups[group].rows[vid].innerHTML = `
                            <td class='control_label date'
                                ${onclick} >${ldate}</td>
                            <td colspan=3 class='control_label source video'
                            >Vid#${n} <a href='#' ${onclick}>Prev.</a> - <a target="_blank" href='${vlink.replace('_768x432','')}'>FullRes</a></td>`;
                    } else {
                        var lab = 'Model results';
                        if (group == 'beach mon reports') {
                            lab = 'PDF';
                            onclick = `onclick="window.open('${vlink}');"`
                        }
                        mom._layerGroups[group].rows[vid].innerHTML = `
                            <td class='control_label date'
                                ${onclick} >${ldate}</td>
                            <td colspan=2 class='control_label source video'
                            ><a href='#' ${onclick}>${lab}</a></td>`;
                        
                    }
                        
                } else {
                    mom._layerGroups[group].rows[id] = L.DomUtil.create(
                        'tr', 'm-basemap-selector', mom._layerGroups[group].table);
                    
                    mom._layerGroups[group].rows[id].innerHTML = `
                        <td class='control_label date'
                            id='${id}-label'
                            title='${attr.title}' ${onclick} >${ldate}</td>
                        <td class='control_label source' 
                            title='${lproduct}'
                            ${onclick}>${lab}</td>
                        <td></td>
                        <td class='control_input'>
                            <input type='${type}' name='${name}'
                                ${onclick} id='${id}-checkbox'
                                title='${attr.title}'>
                        </td>`;
                }
                
                // Add legend
                if (legend) {
                    delay_legend = undefined;
                    delay_legend_id = undefined;
                    mom._layerGroups[group].rows[lid + '_legend'] = L.DomUtil.create(
                        'tr', 'legend', mom._layerGroups[group].table);
                    mom._layerGroups[group].rows[lid + '_legend'].innerHTML = `
                        <td colspan=${header_colspan + 1}>
                            <div class='other-legend' id='${lid}-legend'>
                                ${legend}</div>
                        </td>`
                }
            } else {
                mom._layerGroups[group].rows[id] = L.DomUtil.create(
                    'tr', 'm-basemap-selector', mom._layerGroups[group].table);
                mom._layerGroups[group].rows[id].innerHTML = `
                    <td class='control_label' id='${id}-label' 
                        colspan=${header_colspan} 
                        title='${attr.title}'
                        onClick='onToggleOtherLayerClick(this)' >
                            ${attr.label}
                            <div class='other-legend' id='${id}-legend'>
                                ${attr.legend}</div>
                    </td>

                    <td class='control_input'>
                        <input type='${type}' name='imagery'
                            onClick='onToggleOtherLayerClick(this)'
                            id='${id}-checkbox'
                            title='${attr.title}'>
                    </td>`
                
            }
        });
        
        ///////////////////////////////////////////////////////////////////////
        // Bottom (other/basemap) selector rows
//         addBuffer();
        L.DomUtil.create('tr', 'm-basemap-selector divider', this._layersTable);
        
        this._basemapSelectorRow1 = L.DomUtil.create(
            'tr', 'm-basemap-selector header', this._layersTable);
        this._basemapSelectorRow1.innerHTML= '<td colspan=' + header_colspan + '>Basemap</td><td class="collapse">-</td>';
        this._basemapSelectorRow1.id = 'Background-header';
        
        this._basemapSelectorRows = {};
        var mom = this;
        var tmp = L.DomUtil.create('tr', 'm-basemap-filler', mom._layersTable);
        tmp.innerHTML = '<td colspan=' + header_colspan+1 + '>';
        
        // Add "off" radio option at top of each imagery group
//                 if (group.indexOf('imagery')) {
//         mom._whatever = L.DomUtil.create(
//             'tr','m-basemap-selector', mom._layersTable);
        
//         mom._whatever.innerHTML = [
//             "<td class='control_label' id='off-label' ",
//                 "colspan=" + header_colspan + ' ',
//                 "title='Turn off imagery layer' ",
//                 "onClick='onToggleOtherLayerClick(this)' >Imagery OFF",
//             "<td class='control_label'>",
//                 "<input type='radio' name='imagery' ",
//                     "onClick='onToggleOtherLayerClick(this)' ",
//                     "id='off-checkbox'",
//         "</td>"].join('');
        
        // Other layers
//         var tmp = L.DomUtil.create('tr', 'm-basemap-filler', mom._layersTable);
//         tmp.innerHTML = '<td colspan=' + header_colspan+1 + '>';
//         var tmp2 = L.DomUtil.create('tr','m-basemap-headeroo', mom._layersTable);
//         tmp2.innerHTML = `<td colspan=${header_colspan + 1}>Other</td>`;
//         var keys = Object.keys(mom._baseLayers);
//         keys.sort();
//         $.each(keys, function(i,id) {
//             var attr = mom._baseLayers[id];
//             var lproduct = attr.label.split('_')[2];
//             var group = mom._baseLayers[id].group;
//             if (group != 'other') {
//                 return;
//             }
// //             console.log(attr, i, mom._baseLayers);
//             var onclick = `"onToggleOtherLayerClick(this,'${id}');"`;
//             var tr8 = L.DomUtil.create('tr','m-basemap-selector', mom._layersTable);
//             tr8.innerHTML = `
//                 <td class="control_label" colspan=${header_colspan}
//                     onClick=${onclick} >${lproduct}</td>
//                 <td class='control_label'>
//                     <input type='checkbox' id='${id}-checkbox'
//                         onClick=${onclick} 
//                         value='${i}'>
//                 </td>`;
//             
//             if (attr.legend) {
//                 var tr8_leg = L.DomUtil.create(
//                     'tr', 'legend', mom._layersTable);
//                 tr8_leg.innerHTML = `
//                     <td colspan=${header_colspan + 1}>
//                         <div class='other-legend' id='${id}-legend'>
//                             ${attr.legend}</div>
//                     </td>`;
//                 
//             }
//         });
        
        // Basemap lists
//         var tmp2 = L.DomUtil.create('tr','m-basemap-filler2', mom._layersTable);
//         tmp2.innerHTML = `<td colspan=${header_colspan + 1}></td>`;
        
//         var tmp2 = L.DomUtil.create('tr','m-basemap-headeroo', mom._layersTable);
//         tmp2.innerHTML = `<td colspan=${header_colspan + 1}>Background</td>`;
        
        $.each(basemap_options, function(i,basemap) {
            checked = (i == Object.keys(basemap_options)[0] ? 'checked' : '');
            mom._basemapSelectorRows[i] = L.DomUtil.create(
                'tr', 'm-basemap-selector', mom._layersTable);
            mom._basemapSelectorRows[i].innerHTML = [
                '<td class="control_label" colspan=' + header_colspan,
                ' onClick="selectBasemap(this,' + "'" +  i + "'" + ')" >' + i + '</td>',
                "<td class='control_label'>",
                    "<input type='radio' ",
                        "name='basemap' ",
                        'onClick="selectBasemap(this,' + "'" + i + "'" + ')" ', 
                        "value='" + i + "' " + checked + '>',
                '</td>'].join('');
            
        });
        var tmp = L.DomUtil.create('tr', 'm-basemap-filler', mom._layersTable);
        tmp.innerHTML = '<td colspan=' + header_colspan+1 + '>';
        
        container.appendChild(form);
        

    },

    _getLayer: function (id) {
        for (var i = 0; i < this._layers.length; i++) {
            if (this._layers[i] && L.stamp(this._layers[i].layer) === id) {
                    return this._layers[i];
            }
        }
    },

    _addLayer: function (layer, name, overlay) {
//         console.log(layer);
        layer.on('add remove', this._onLayerChange, this);

        this._layers.push({
            layer: layer,
            name: name,
            overlay: overlay
        });

        if (this.options.sortLayers) {
            this._layers.sort(L.bind(function (a, b) {
                return this.options.sortFunction(a.layer, b.layer, a.name, b.name);
            }, this));
        }

        if (this.options.autoZIndex && layer.setZIndex) {
            this._lastZIndex++;
            layer.setZIndex(this._lastZIndex);
        }
    },
    _update: function () {
        if (!this._container) { return this; }

//         L.DomUtil.empty(this._baseLayersList);
//         L.DomUtil.empty(this._overlaysList);

        var baseLayersPresent, overlaysPresent, i, obj, baseLayersCount = 0;

        for (i = 0; i < this._layers.length; i++) {
            obj = this._layers[i];
            this._addItem(obj);
            overlaysPresent = overlaysPresent || obj.overlay;
            baseLayersPresent = baseLayersPresent || !obj.overlay;
            baseLayersCount += !obj.overlay ? 1 : 0;
        }

    },
//     _update: function () {
//         if (!this._container) { return this; }
// 
// //         L.DomUtil.empty(this._baseLayersList);
// //         L.DomUtil.empty(this._overlaysList);
// 
//         var baseLayersPresent, overlaysPresent, i, obj, baseLayersCount = 0;
// 
//         for (i = 0; i < this._layers.length; i++) {
//             obj = this._layers[i];
//             this._addItem(obj);
//             overlaysPresent = overlaysPresent || obj.overlay;
//             baseLayersPresent = baseLayersPresent || !obj.overlay;
//             baseLayersCount += !obj.overlay ? 1 : 0;
//         }
//         
//                 
//         ///////////////////////////////////////
//         // After adding items, add a Toggle All for the overlays
// 
//         var input = document.createElement('input');
//         input.type = 'checkbox';
//         input.className = 'leaflet-control-layers-selector';
//         input.layerId = 'toggle';
//         // Modify the onclick event to check all layers/uncheck
//         L.DomEvent.on(input, 'click', this._onToggleAllClick, this);
//         
//         // Checkbox label
//         var name = document.createElement('div');
//         name.innerHTML = 'All<br>';
//         
//         // Helps from preventing layer control flicker when checkboxes are disabled
//         // https://github.com/Leaflet/Leaflet/issues/2771
//         var holder = document.createElement('div');
//         holder.className = 'layerLabelAndCheck footer';
//         holder.appendChild(name);
//         holder.appendChild(input);
//         
//         var label = document.createElement('label');
//         label.appendChild(holder);
// 
//         this._overlaysList.appendChild(label);
//         
//         ///////////////////////////////////////
//         // Add an 'off' radio option for base layers
//         
//         var input = this._createRadioElement('leaflet-base-layers', false);
//         input.layerId = 'none';
//         // Modify the onclick event to check all layers/uncheck
//         L.DomEvent.on(input, 'click', this._onInputClick, this);
// 
// 
//         var name = document.createElement('div');
//         name.innerHTML = 'Off<br>';
//         
//         // Helps from preventing layer control flicker when checkboxes are disabled
//         // https://github.com/Leaflet/Leaflet/issues/2771
//         var holder = document.createElement('div');
//         holder.className = 'layerLabelAndCheck footer';
//         holder.appendChild(name);
//         holder.appendChild(input);
//         
//         // Wrap everything in a label
//         var label = document.createElement('label');
//         label.appendChild(holder);
// 
//         this._baseLayersList.appendChild(label);
//         
// 
//     },

    _onLayerChange: function (e) {
        if (!this._handlingClick) {
            this._update();
        }

        var obj = this._getLayer(L.stamp(e.target));

        // @namespace Map
        // @section Layer events
        // @event baselayerchange: LayersControlEvent
        // Fired when the base layer is changed through the [layer control](#control-layers).
        // @event overlayadd: LayersControlEvent
        // Fired when an overlay is selected through the [layer control](#control-layers).
        // @event overlayremove: LayersControlEvent
        // Fired when an overlay is deselected through the [layer control](#control-layers).
        // @namespace Control.Layers
        var type = obj.overlay ?
                (e.type === 'add' ? 'overlayadd' : 'overlayremove') :
                (e.type === 'add' ? 'baselayerchange' : null);

        if (type) {
                this._map.fire(type, obj);
        }
    },

    // IE7 bugs out if you create a radio dynamically, so you have to do it this hacky way (see http://bit.ly/PqYLBe)
    _createRadioElement: function (name, checked) {

        var radioHtml = '<input type="radio" class="leaflet-control-layers-selector" name="' +
            name + '"' + (checked ? ' checked="checked"' : '') + '/>';

        var radioFragment = document.createElement('div');
        radioFragment.innerHTML = radioHtml;

        return radioFragment.firstChild;
    },

    _addItem: function (obj) {
        var label = document.createElement('label'),
            checked = this._map.hasLayer(obj.layer),
            input,
            input_stuff;
            
        var name = document.createElement('span');
        var holder = document.createElement('div');
        
        holder.className = 'layerLabelAndCheck';
//         if (Object.keys(special_cases).indexOf(obj.name) > -1) {
//             holder.title = special_cases[obj.name].description; 
//         }
        
        var layerId = L.stamp(obj.layer);
        
        if (obj.overlay) {
            input_stuff = document.createElement('div');
            input_stuff.className = 'layerCheckbox';
            if (checked) {
                input_stuff.style.backgroundColor = colormap[obj.name];
            } else {
                input_stuff.style.backgroudnColor = 'inherit';
            }
            
            input = document.createElement('input');
            input.type = 'checkbox';
            input.className = 'leaflet-control-layers-selector';
            input.defaultChecked = checked;
            input_stuff.appendChild(input);
            
            name.innerHTML = ' ' + obj.name;
        } else {
            input = this._createRadioElement('leaflet-base-layers', false);
            input.id = 'extent-imagery-radio-' + obj.name;
            input.dataset.layerId = layerId;
//             if (obj.name == default_year) {
//                 input.checked = true;
//             }
            name.innerHTML = ' ';
            input_stuff = input;
        }

        input.layerId = layerId;

        L.DomEvent.on(input, 'click', this._onInputClick, this);

        // Helps from preventing layer control flicker when checkboxes are disabled
        // https://github.com/Leaflet/Leaflet/issues/2771

        var marginTop = 0;
//         var layerIndex = shoreline_years.indexOf(obj.name);
// 
// //         if (layerIndex < (shoreline_years.length -1)) {
// //             marginTop = shoreline_years[layerIndex-1] - shoreline_years[layerIndex];
// //         }
//         if (layerIndex < (shoreline_years.length -1)) {
//             marginTop = Number(String(shoreline_years[layerIndex+1]).substr(-4)) - 
//                 Number(String(shoreline_years[layerIndex]).substr(-4));
//         }

        holder.style.marginTop = marginTop*0.8;
        
        label.appendChild(holder);
        holder.appendChild(name);
        holder.appendChild(input_stuff);

        // TODO: instead of append to container, insert to appropriate place in 
        // layers table
        // * get appropriate row
        // * get approprigate column
        var container = obj.overlay ? this._overlaysList : this._baseLayersList;
        if (container) {
            container.appendChild(label);
        }

        this._checkDisabledLayers();
        return label;
    },

    _onToggleAllClick: function (event) {
        var turn_on = event.target.checked;
        var inputs = this._form.getElementsByTagName('input');
        var inputs = this._form.getElementsByClassName('leaflet-control-layers-selector');
        var mom = this;
        for (var i = inputs.length - 1; i >= 0; i--) {
            input = inputs[i];
            if (input.layerId != 'toggle' && 
                Object.keys(mom._baseLayers).indexOf(input.layerId) == -1 &&
                input.type == 'checkbox') {
                input.checked = turn_on;
            }
        }
        this._onInputClick();
        
        return;
    },
    
    _onInputClick: function () {
        var form = this._form;
        var inputs = form.getElementsByTagName('input'),
            input, layer, hasLayer;
        var addedLayers = [],
            removedLayers = [];
        var mom = this;
        this._handlingClick = true;

        var image_checked = false;
        for (var i = inputs.length - 1; i >= 0; i--) {
            input = inputs[i];
            if (['toggle','none',undefined].concat(Object.keys(this._baseLayers)
                ).indexOf(input.layerId) == -1) {
                var radioLayer;
                var obj = this._getLayer(input.layerId)
                layer = obj.layer;
                hasLayer = this._map.hasLayer(layer);
            
//                 // Get corresponding radio
//                 if (input.type == 'checkbox') {
//                     radioLayer = form.getElementById('extent-imagery-radio-' + obj.name);
//                     
//                 }
//             

                if (input.checked && !hasLayer) {
                    addedLayers.push(layer);

                } else if (!input.checked && hasLayer) {
                    removedLayers.push(layer);
                }

                if (input.checked && input.type == 'checkbox') {
                    input.parentNode.style.backgroundColor = colormap[obj.name];
                } else {
                    input.parentNode.style.backgroundColor = 'inherit';
                }
                
                if (input.checked && input.type == 'radio') {
                    image_checked = true;
//                     document.getElementById('imagery_year').innerHTML = obj.name;
                }
            }
        }

//         if (!image_checked) {
//             document.getElementById('imagery_year').innerHTML = 'None selected';  
//         }
        
        // Bugfix issue 2318: Should remove all old layers before readding new ones
        for (i = 0; i < removedLayers.length; i++) {
            this._map.removeLayer(removedLayers[i]);
        }
        for (i = 0; i < addedLayers.length; i++) {
            this._map.addLayer(addedLayers[i]);
        }
        
        this._handlingClick = false;

        this._refocusOnMap();
    },

    _checkDisabledLayers: function () {
        var inputs = this._form.getElementsByTagName('input'),
            input,
            layer,
            zoom = this._map.getZoom();
        var mom = this;
            
        for (var i = inputs.length - 1; i >= 0; i--) {
            input = inputs[i];
            if (['toggle','none',undefined].concat(Object.keys(mom._baseLayers)
                ).indexOf(input.layerId) == -1) {
                
                layer = this._getLayer(input.layerId).layer;
                input.disabled =
                    (layer.options.minZoom !== undefined && zoom < layer.options.minZoom) ||
                    (layer.options.maxZoom !== undefined && zoom > layer.options.maxZoom);
            }
        }
    },

    });
