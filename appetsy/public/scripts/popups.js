var current_fan_key = null;

$(document).ready(function() {
    $(".fan_clicker").live("click", function() {
        if ($(this).attr("key") == current_fan_key) {
            $("#fan_info").fadeOut();
            current_fan_key = null;
        } else {
            current_fan_key = $(this).attr("key");

            var clicker_pos = $(this).position()
            var popup_left = clicker_pos.left
            if (popup_left + 440 > window.innerWidth) {
                popup_left = window.innerWidth - 440;
            }
            
            $("#fan_info").html('<div style="padding: 6px">Loading...</div>');

            $("#fan_info").css("left", popup_left);
            $("#fan_info").css("width", 400)
            $("#fan_info").css("top", clicker_pos.top + $(this).height() + 4);
            
            $("#fan_info").fadeIn();
            
            jQuery.get("/fans/" + current_fan_key,
                       null,
                       function(data, status) {
                            $("#fan_info").html(data);
                            $("#popup_fan_details").load("/fans/" + current_fan_key + "/faves")
                       }
            )
        }
        return false;
    });
});


