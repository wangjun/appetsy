$(".popup_result").unbind()
$(".popup_result").live("click", function(){
    $("#popup_fan_details").html('Loading...')
    
    $("#popup_fan").load("/fans/" + $(this).attr("key") + "/details")
    $("#popup_fan_details").load("/fans/" + $(this).attr("key") + "/faves")
    return false;
});