var current_goods_key = null;
var current_expense_key = null;
var refreshInterval = 1000 * 60;
var refreshTimer = null;
var currentBalanceMonth = null;
var currentFansTodayView = "persons";

$(document).ready(function() {
    $("#add_expense_button").click(function(){
        $('#add_expense').css('left', $("#add_expense_button").position().left)
        $('#add_expense').css('top', $("#add_expense_button").position().top + 24)
        $('#add_expense').show();
        document.forms["add_expense_form"].reset()

        $("#expense_date_edit").val(new Date().toLocaleFormat("%d-%b"));
        preview_date("#expense_")

        $('#expense_name').focus();
    });

    $("#add_good_button").click(function() {
        $('#add_good').css('left', $("#add_good_button").position().left)
        $('#add_good').css('top', $("#add_good_button").position().top + 24)

        $('#add_good').show();
        document.forms["add_good_form"].reset()

        $("#creation_date_edit").val(new Date().toLocaleFormat("%d-%b"));
        preview_date("#creation_")
        $('#good_name').focus();

    })

    $("#cancel_new_good").attr("onclick", "");
    $("#cancel_new_good").click(function(event){
         $("#add_good").fadeOut();
    })

    $("#save_new_good").click(function(event) {
        $("#save_new_good").attr("disabled","disabled");
        $("#cancel_new_good").attr("disabled","disabled");

        jQuery.post("/goods",
                    $("#add_good_form").serialize(),
                    function(data, status) {
                        if (status == "success") {
                            var key = data;
                            refreshActiveList(null, key);
                            refreshProgressBox(null);
                        } else {
                            alert(data);
                        }
                    });
        return false;
    });


    $("#cancel_new_expense").attr("onclick", "");
    $("#cancel_new_expense").click(function(event){
         $("#add_expense").hide();
    })

    $("#save_new_expense").click(function(event) {
        $("#save_new_expense").attr("disabled","disabled");
        $("#cancel_new_expense").attr("disabled","disabled");
        jQuery.post("/expenses",
                    $("#add_expense_form").serialize(),
                    function(data, status) {
                        if (status == "success") {
                            var key = data;
                            refreshActiveExpenses(null, key);
                        } else {
                            alert(data);
                        }

                    });
        return false;
    });


    $(".tabs a").click(function(event) {
        $(".tabs a").removeAttr("class")
        $(this).attr("class", "active")

        $(".pages .page").hide();
        $("#" + $(this).attr("page")).show();
    });

    applyPopups();

    viewStats.plot(stats);

    refreshTimer = setTimeout(refreshContent, refreshInterval); //once in a while
})

function applyPopups() {
    $("#person_link").live("click", function() {
        $("#item_box").hide();
        if ($("#person_box").is(':hidden')) {
            $("#fan_info").hide();
            $("#person_box").fadeIn();
        }
        currentFansTodayView = "persons"
    });
    $("#item_link").live("click", function() {
        $("#person_box").hide();
        if ($("#item_box").is(':hidden')) {
            $("#fan_info").hide();
            $("#item_box").fadeIn();
        }
        currentFansTodayView = "items"
    });



    $(".active_good_link").live("click", function(event){
        var key = $(this).attr("key")

        if (current_goods_key == key) {
            $("#edit_good_form").hide();
            current_goods_key = null;
            return false;
        }

        current_goods_key = key;

        var link = this;
        $("#edit_good_form").html("Loading...")
        $("#edit_good_form").css("left", $(link).offset().left)
        $("#edit_good_form").css("top", $(link).offset().top + $(link).height() + 4)
        $("#edit_good_form").show();

        jQuery.get("/goods/" + key + "/edit",
                   function(data, status) {
                        $("#edit_good_form").html(data);

                        $("#cancel_good").attr("onclick", "");
                        $("#cancel_good").click(function(event){
                            $("#edit_good_form").hide();
                            current_goods_key = null;
                        })

                        $("#save_good").click(function(event) {
                            $("#save_good").attr("disabled","disabled");
                            $("#cancel_good").attr("disabled","disabled");

                            current_panel = key;
                            jQuery.post("/goods/" + key,
                                        $("#goods_form").serialize(),
                                        function(data, status) {
                                            if (status == "success") {
                                                var key = data;
                                                current_goods_key = null;
                                                refreshActiveList(null, key);
                                                refreshProgressBox(null)
                                            } else {
                                                alert(data);
                                            }
                                        });
                            return false;
                        });
                   });


       return false;
    });

    $(".active_expense_link").live("click", function(event) {
        var key = $(this).attr("key")

        if (current_expense_key == key) {
            $("#edit_expense_form").hide();
            current_expense_key = null;
            return false;
        }

        current_expense_key = key;

        var link = this;
        $("#edit_expense_form").html("Loading...")
        $("#edit_expense_form").css("left", $(link).position().left)
        $("#edit_expense_form").css("top", $(link).position().top + $(link).height() + 4)
        $("#edit_expense_form").show();

        jQuery.get("/expenses/" + key + "/edit",
                   null,
                   function(data, status) {
                        var pos = $(link).position().left;
                        $("#edit_expense_form").html(data);

                        $("#cancel_expense").attr("onclick", "");
                        $("#cancel_expense").click(function(event){
                            $("#edit_expense_form").hide();
                            current_expense_key = null;
                        })

                        $("#save_expense").click(function(event) {
                            $("#save_expense").attr("disabled","disabled");
                            $("#cancel_expense").attr("disabled","disabled");

                            current_panel = key;
                            jQuery.post("/expenses/" + key,
                                        $("#expenses_form").serialize(),
                                        function(data, status) {
                                            if (status == "success") {
                                                current_expense_key = null;
                                                var key = data;
                                                refreshActiveExpenses(null, key);
                                            } else {
                                                alert(data);
                                            }

                                        });
                            return false;
                        });
                   });
       return false;
    });


    // the plans form
    $("#planned_production").live("click", function() {
        $(this).parent().attr("prev_val", $(this).val()); //backup
        $("#plans_form button[type=submit]").text("Saglabāt")
        $(this).parent().addClass("editing");
        $(this).select();
    });

    $("#plans_form button[type=reset]").live("click", function() {
        if ($(this).parent().attr("prev_val"))
            $("#planned_production").val($(this).parent().attr("prev_val"))

        $(this).parent().removeClass("editing");
    });

    var onPlansSubmit = function() {
        jQuery.post("/plans/update",
                    $(this).parent().serialize(),
                    function() {
                        $(this).parent().removeClass("editing");
                        refreshProgressBox(null)
                    }
        );
        $("#plans_form button[type=submit]").text("Glabāju...")
        return false;
    }

    $("#plans_form").live("submit", onPlansSubmit);
    $("#plans_form button[type=submit]").live("click", onPlansSubmit);
}

function refreshActiveList(callback, spotlight_key) {
    var waitingFor = 2;

    var onDone = function() {
        waitingFor -= 1
        if (waitingFor == 0) {
            if (callback)
                callback();
        } else {
            hideForms();
        }
    }

    var hideForms = function() {
        $("#edit_good_form").hide();
        $("#save_good").removeAttr("disabled");
        $("#cancel_good").removeAttr("disabled");

        $("#add_good").hide();
        $("#save_new_good").removeAttr("disabled");
        $("#cancel_new_good").removeAttr("disabled");
    }

    var refresh_active = function() {
        $("#active_goods").load("/goods/active?" + encodeURI("spotlight=" +spotlight_key), onDone);
    }

    // prioritize the tab we are currently viewing
    if ($(".tabs a.active").attr("id") == "overview_tab") {
        refresh_active(onDone, spotlight_key);
        loadBalance(spotlight_key, onDone);
    } else {
        loadBalance(spotlight_key, onDone);
        refresh_active(onDone, spotlight_key);
    }
}

function refreshActiveExpenses(callback, spotlight_key) {
    var waitingFor = 2;

    var onDone = function() {
        waitingFor -= 1
        if (waitingFor == 0) {

            if (callback)
                callback();
        } else {
            // hide form on first result
            $("#edit_expense_form").hide();
            $("#save_expense").removeAttr("disabled");
            $("#cancel_expense").removeAttr("disabled");

            $("#add_expense").hide();

            $("#save_new_expense").removeAttr("disabled");
            $("#cancel_new_expense").removeAttr("disabled");
        }
    }

    var refresh_active = function() {
        $("#active_goods").load("/goods/active?" + encodeURI("spotlight=" +spotlight_key), onDone);
    }

    // prioritize the tab we are currently viewing
    if ($(".tabs a.active").attr("id") == "overview_tab") {
        refresh_active();
        loadBalance(spotlight_key, onDone);
    } else {
        loadBalance(spotlight_key, onDone);
        refresh_active();
    }
}

function refreshContent() {
    $("#status").fadeIn();
    var waitingFor = 6;

    var onDone = function() {
        waitingFor -= 1
        if (waitingFor == 0) {
            $("#status").fadeOut();
            clearTimeout(refreshTimer);
            refreshTimer = setTimeout(refreshContent, refreshInterval); //once in a while
        }
    }

    var refresh_balance = function() {
        loadBalance(null, onDone);
    }

    var refresh_active = function() {
        $("#active_goods").load("/goods/active", onDone);
        $("#active_expenses").load("/expenses/active", onDone);
    }

    // invisible tab we will refresh last
    var refreshFirst = refresh_active;
    var refreshLast = refresh_balance;
    if ($(".tabs a.active").attr("id") == "balance_tab") { //swap if on balance tab
        var z = refreshFirst;
        refreshFirst = refreshLast;
        refreshLast = z;
    }


    refreshFirst();

    $("#sold_and_featured").load("/sold_and_featured_today", onDone);
    $("#fans_today").load("/fans_today?page=" + encodeURIComponent(currentFansTodayView), onDone);

    refreshViews(onDone);
    refreshProgressBox(onDone);
    refreshLast();
}

function changeShop(shop_id) {
    jQuery.post("/shop/" + shop_id, function(){
        refreshContent();
    })
}


function refreshProgressBox(callback) {
    jQuery.get("/progress_box",
        null,
        function(data, status) {
             $("#progress_box").html(data);
             if (callback != null) {
                callback();
             }
        }
    );

}

function refreshViews(callback) {
    jQuery.getJSON("/recent_views",
        null,
        function(stats, status) {
             viewStats.plot(stats);
             if (callback != null) {
                callback();
             }
        }
    );
}

function preview_date(prefix) {
    //
    var d1 = Date.parse($(prefix + "date_edit").val());
    if (d1) {
        $(prefix+"date_preview").html(d1.toString('dddd, MMMM d, yyyy'));
        $(prefix+"date").val(d1.toString('d-MMM-yyyy'));
    } else {
        $(prefix+"date_preview").html("");
        $(prefix+"date").val("");
    }
}


function edit_show_sold_details() {
    if ($("#edit_good_status").val() == "sold") {
        $("#edit_sale_date_row").show();
        $("#edit_sale_price_row").show();
        $("#edit_sale_date_edit").value = new Date().toLocaleFormat("%d-%b");
        $("#edit_sale_date_edit").focus();
        $("#edit_sale_date_edit").select();
    } else {
        $("#edit_sale_date_row").hide();
        $("#edit_sale_price_row").hide();
        $("#edit_sale_date_edit").value = "";
    }
    preview_date("edit_sale_");
}


function show_sold_details() {
    if ($("#good_status").val() == "sold") {
        $("#sale_date_row").show();
        $("#sale_price_row").show();
        $("#sale_date_edit").value = new Date().toLocaleFormat("%d-%b");
        $("#sale_date_edit").focus();
        $("#sale_date_edit").select();
    } else {
        $("#sale_date_row").hide();
        $("#sale_price_row").hide();
        $("#sale_date_edit").value = "";
    }
    preview_date("sale_");
}

var viewStats = {
    r: null,
    fontConfig: {font: '10px Georgia', fill: "#999", "text-anchor": "start"},
    width: 380,
    height: 150,
    margin: {top: 0, right: 0, bottom: 20, left: 20},
    div: function() {return document.getElementById("recent_views");},



    plot: function(stats){
        if (!this.r) {
            this.r = Raphael(this.div(), this.width, this.height);
        }
        r = this.r;

        r.clear();

        var graph_x = this.margin.left;
        var graph_y = this.margin.top;
        var graph_width = this.width - this.margin.left - this.margin.right;
        var graph_height = this.height - this.margin.top - this.margin.bottom;
        var max_bar_height = graph_height * 0.8;

        var bar_width = Math.round(graph_width / (stats.views.length + 1)) - 2;

        var x = graph_x;

        // max label
        var max_label = r.text(graph_x - 20, graph_y + graph_height - max_bar_height, stats.max_views)
                         .attr(this.fontConfig)
                         .attr({fill: "#666", "text-anchor": "start"});

        // max line
        var maxline = r.path("M" + graph_x + " " + (graph_y + graph_height - max_bar_height + 0.5) +
                             "L" + (graph_x + graph_width) + " " + (graph_y + graph_height - max_bar_height - 1))
        maxline.attr({stroke: "#fff", "stroke-width": "1"})

        var backgrounds = r.set()


        var freeX = [];
        var placeLabel = function(x, label) {
            var freePos = 0;
            if (freeX) {
                freePos = -1;
                for (var i in freeX) {
                    if (freeX[i] < x) {
                        freePos = i;
                        break;
                    }
                }

                if (freePos == -1) {
                    // did not find free spot, let's add another one to the bottom
                    freeX[freeX.length] = 0;
                    freePos = freeX.length - 1;
                }

            }

            var positionedLabel  = r.text(x, freePos * 12 + graph_y + 10, label)
                                    .attr({font: '10px Georgia', fill: "#999", "text-anchor": "start"})
                                    .attr({fill: "#666"});
            freeX[freePos] = x + positionedLabel.getBBox().width;
        }


        for (var key in stats.views) {
            var view = stats.views[key];
            view.time = new Date.parse(view.time);

            // event background bar
            if (view.events.length > 0) {
                backgrounds.push(r.rect(x, graph_y, bar_width, graph_height)
                                   .attr({fill: "#E2F2ED", "stroke": "#E2F2ED"}))
            }

            // view bar
            var y = Math.max(max_bar_height * view.rel_views, 1);
            var bar = r.rect(x, graph_y + graph_height - y, bar_width, y).attr({fill: "#D0D8A5", "stroke": "#D0D8A5"})

            $(bar.node).click(function() {
                alert("zumm")
            });

            // fave bar
            var y = max_bar_height * (view.faves / view.views) * view.rel_views;
            r.rect(x, graph_y + graph_height - y, bar_width, y).attr({fill: "#BDC982", "stroke": "#D0D8A5"})


            // events
            if (view.events.length > 0) {
                var prevText = null;
                var prevCount = 0;
                for (var i = 0; i < view.events.length; i++) {
                    var label = view.events[i]

                    if (prevText && prevText != label) {
                        if (prevCount > 1)
                            prevText += " (" + prevCount + ")";

                        placeLabel(x+1, prevText)
                        prevCount = 1;
                    } else {
                        prevCount +=1;
                    }
                    prevText = label;
                }

                if (prevText) { // and the last one
                    if (prevCount > 1)
                        prevText += " (" + prevCount + ")";

                    placeLabel(x+1, prevText);
                }
            }


            // hour label
            if (view.time.getHours() % 4 == 0) {
                var am = view.time.getHours() < 12 ? "AM":"PM"
                var hour = view.time.getHours() % 12
                if (hour == 0) hour = 12;

                var hourLabel = hour + am;

                r.text(x+1, graph_y + graph_height + 10, hourLabel)
                 .attr(this.fontConfig)
                 .attr({fill: "#666"});
            }

            x += bar_width + 2;

        }

        backgrounds.toBack();
    }
}


var balanceGraph = {
    r: null,
    fontConfig: {font: '10px Georgia', fill: "#999", "text-anchor": "start"},
    width: 150,
    height: 60,
    margin: {top: 0, right: 0, bottom: 20, left: 20},
    div: function() {return document.getElementById("balance_graph");},



    plot: function(stats){
        this.r = Raphael(this.div(), this.width, this.height);

        r = this.r;

        r.clear();

        var graph_x = this.margin.left;
        var graph_y = this.margin.top;
        var graph_width = this.width - this.margin.left - this.margin.right;
        var graph_height = this.height - this.margin.top - this.margin.bottom;
        var max_bar_height = graph_height * 0.8;

        var bar_width = Math.round(graph_width / stats.length) - 2;
        var x = graph_x;


        for (var key in stats) {
            var stat = stats[key];
            // view bar
            var y = max_bar_height * stat.rel_total;

            var bar = r.rect(x, graph_y + graph_height - y, bar_width, y).attr({fill: "#D0D8A5", "stroke": "#D0D8A5"})
            // transparent bar on top of existing one to catch mouse
            var mouseCatcher = r.rect(x, graph_y, bar_width, graph_height)
                                 .attr({fill: "#000", "stroke": "#000", "opacity": 0})


            var month_label = r.text(graph_x + graph_width, graph_y + graph_height + 10, stat.month)
                               .attr(this.fontConfig)
                               .attr("text-anchor", "end")
                               .attr({fill: "#666"}).hide();

            // and now a closure for events
            (function (mouseCatcher, bar, month_label, action) {
                $(mouseCatcher.node).hover(
                    function() {
                        bar.attr({fill: "#eee", stroke: "#eee"})
                        month_label.show();
                    },
                    function() {
                        bar.attr({fill: "#D0D8A5", stroke: "#D0D8A5"})
                        month_label.hide();
                    }
                )

                $(mouseCatcher.node).click(function(){
                    action();
                });
            })(mouseCatcher, bar, month_label, stat.action);


            x += Math.round(graph_width / stats.length);

        }
    }
}

function loadBalance(spotlight, callback, date){
    if (date)
        currentBalanceMonth = date;

    $("#balance").load("/expenses/balance?" + encodeURI("spotlight=" + (spotlight || "") + "&month=" + (currentBalanceMonth || "")), callback);
}
