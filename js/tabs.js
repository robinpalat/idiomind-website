
function getCookie(cname) {
	var name = cname + "=";
	var decodedCookie = decodeURIComponent(document.cookie);
	var ca = decodedCookie.split(';');
	for(var i = 0; i <ca.length; i++) {
		var c = ca[i];
		while (c.charAt(0) == ' ') {
			c = c.substring(1);
		}
		if (c.indexOf(name) == 0) {
			return c.substring(name.length, c.length);
		}
	}
	return "";
}


function openTab(evt, tabName) {
    var i, tabcontent, tablinks;
    tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    
    if (tabName=="Favorites") {

		var faves = getCookie('Topics_fav');
		
		var faves = faves.split('|')
		
		for (i = 0, len = faves.length, text = ""; i < len; i++) { 
			text += faves[i] + "<br>";
		}

		alert(faves)
	}
    
    
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";
}


openTab(event, 'Latest')
