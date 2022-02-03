// close message UI
if (document.getElementById( "flash-message" )) {

     // document.getElementById(id).style.property = new style
    var closeButton = document.getElementById( "flash-message" ),
        message = closeButton.parentElement;

    closeButton.onclick = function() { message.style.display = "none"; };

}
