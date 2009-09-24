function escapeHTML (str) {    var div = document.createElement('div');
    var text = document.createTextNode(str);
    div.appendChild(text);
    return div.innerHTML;}
function longpoll(url,callback) {
    $.get(url, null, function(data, status){if (callback(data,status) != false) { longpoll(url,callback)}}, "json");
}





//userlist
function userlist(listurl,callback) {
    ul = $("<ul></ul>");
    callback.call(ul);
    makeRelay(listurl+"/relay", ["userlogin", "userlogout"], function(url) {
        $.post(listurl, JSON.stringify({request:"getusers"}), function(data,status){ //i rearranged this one, to avoid a "race condition"
            if (data.status == "ok") {
                $.each(data.users, function(){
                    ul.append("<li>"+escapeHTML(this)+"</li>");
                });

            }
        }, "json");
        longpoll(url, function(data,status){
            if (data.status == "ok") {
                if (data.event == 'userlogin') {
                    if ($("li:contains('"+data.user+"')",ul).length > 0)
                        return true;
                    ul.append("<li>"+escapeHTML(data.user)+"</li>");
                    return true;
                } else if(data.event == 'userlogout') {
                    $("li:contains('"+escapeHTML(data.user)+"')",ul).remove();
                    
                }
            }
            else
                return false;
        });
    });

}


function chatwidget(chaturl,callback) {
    div = $("<div style='width: 100%; height: 100%; '></div>");
    callback.call(div);
    textdiv = $("<div style='height: 90%; width: 100%; padding: 0px; margin: 0px; overflow:auto'></div>");
    input = $("<form><input type='text' style='width: 100%; height: 10%;' /></form>").append("");
    div.append(textdiv[0]).append(input[0]);
    input.submit(function(){
        $.post(chaturl, JSON.stringify({request: 'newmessage', 'msg': $("input", input)[0].value}), function(){
            $("input", input)[0].value = "";
        }, "json");
        return false;
    });
    $.post(chaturl, JSON.stringify({request: 'getlog', lines: 20}), function(data,status){
        if (data.status == "ok") {
            $.each(data.messages,function(){
                textdiv.append("<div><span style='color:#ccc;'>"+escapeHTML(this.username)+"</span> - "+escapeHTML(this.message)+"<span class='endofmessage'> </span></div>")
                textdiv.scrollTo($("div:last > span.endofmessage", textdiv));
            });
        }
    }, "json");
    makeRelay(chaturl+"/relay", ['newmessage'], function(url){
        longpoll(url, function(data,status){
            if (data.status == "ok") {
                textdiv.append("<div><span style='color:red;'>"+escapeHTML(data.message.username)+"</span> - "+escapeHTML(data.message.message)+"<span class='endofmessage'> </span></div>")
                textdiv.scrollTo($("div:last > span.endofmessage", textdiv), 500);
                return true;
            }
            return false;
        });
    });
}
