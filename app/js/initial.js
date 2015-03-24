require(['jquery', 'configure', 'common', 'Dropdown', 'OnOff', 'bootstrap'],
function ($, configure, common, Dropdown, OnOff)
{
    var LICENSE_TIMEOUT = 1000; // 1 sec;
    var setupDone = false;

    /*
     * inputValid()
     * Return whether or not an input field has been filed in (at all) by id.
     */
    function inputValid(id) {
        return ($('#'+id).val().length > 0);
    }

    /*
     * gatherData()
     */
    function gatherData() {
        var data = {};
        data['license-key'] = $('#license-key').val();
        $.extend(data, configure.gatherURLData());
        $.extend(data, configure.gatherTableauURLData());
        $.extend(data, configure.gatherAdminData());
        $.extend(data, configure.gatherReadOnlyData());
        $.extend(data, configure.gatherMailData());
        $.extend(data, configure.gatherSSLData());
        $.extend(data, configure.gatherTzData());
        return data;
    }

    /*
     * save_callback()
     * Callback when the save AJAX call was successfully sent to the server.
     * NOTE: the *data* may still have an error.
     */
    function save_callback(data) {
        if (data['status'] == 'OK') {
            window.location.replace("/");
        }

        var error = data['error'] || 'Unknown server error';
        $('div.setup-page').prepend('<p class="error">' + error + '</p>');
    }

    /*
     * save()
     * Callback for the 'Save' button.
     */
    function save() {
        var data = {'action': 'save'}
        $.extend(data, gatherData());
        $.ajax({
            type: 'POST',
            url: '/open/setup',
            data: data,
            dataType: 'json',

            success: save_callback,
            error: function (jqXHR, textStatus, errorThrown) {
                alert(this.url + ": " +
                      jqXHR.status + " (" + errorThrown + ")");
            }
        });
    }

    /*
     * testMail()
     * Callback for the 'Test Email' button.
     */
    function testMail() {
        $('#mail-test-message').html("");
        $('#mail-test-message').addClass('hidden');
        $('#mail-test-message').removeClass('green red');

        var data = {'action': 'test'}
        $.extend(data, configure.gatherMailData());
        data['test-email-recipient'] = $('#test-email-recipient').val();

        var result = {};
        $.ajax({
            type: 'POST',
            url: '/open/setup',  /* fixme - maybe /open/setup/mail? */
            data: data,
            dataType: 'json',
            async: false,

            success: function(data) {
                result = data;
            },
            error: function (jqXHR, textStatus, errorThrown) {
                alert(this.url + ": " +
                      jqXHR.status + " (" + errorThrown + ")");
            }
        });

        if (result['status'] == 'OK') {
            $('#mail-test-message').html("OK");
            $('#mail-test-message').addClass('green');
            $('#mail-test-message').removeClass('red hidden');
        } else {
            var html = 'FAILED';
            if (result['error'] != null && result['error'].length > 0) {
                html += ': ' + result['error'];
            }
            $('#mail-test-message').html(html);
            $('#mail-test-message').addClass('red');
            $('#mail-test-message').removeClass('green hidden');
        }
    }

    /*
     * maySave()
     * Test input and return true/false.
     */
    function maySave(data) {
        if (!setupDone) {
            return false;
        }
        if (!common.validURL(data['server-url'])) {
            return false;
        }
        if (!common.validURL(data['tableau-server-url'])) {
            return false;
        }
        if (data['license-key'].length < 2) { // FIXME //
            return false;
        }
        if (!configure.validAdminData(data)) {
            return false;
        }
        if (!configure.validMailData(data)) {
            return false;
        }
        if (!configure.validSSLData(data)) {
            return false;
        }
        return true;
    }

    /*
     * mayTest()
     * Test input and return true/false.
     */
    function mayTest(data) {
        var recipient = $('#test-email-recipient').val();
        if (!common.validEmail(recipient)) {
            return false;
        }
        return configure.validMailData(data);
    }

    /*
     * validate()
     * Enable/disable the 'Save' button based on the field values.
     */
    function validate() {
        var data = gatherData();
        if (maySave(data)) {
            $('#save').removeClass('disabled');
        } else {
            $('#save').addClass('disabled');
        }

        if (mayTest(data)) {
            $('#test-mail').removeClass('disabled');
        } else {
            $('#test-mail').addClass('disabled');
        }
    }

    function setup(data)
    {
        Dropdown.setupAll(data);
        OnOff.setup();

        $('#save').bind('click', save);
        $('#test-mail').bind('click', testMail);

        $('#server-url').val(data['server-url']);
        $('#tableau-server-url').val(data['tableau-server-url']);
        $('#alert-email-name').val(data['alert-email-name']);
        $('#alert-email-address').val(data['alert-email-address']);
        $('#license-key').val(data['license-key']);
        $('#readonly-password').val(data['readonly-password']);

        /* validation */
        Dropdown.setCallback(validate);
        Dropdown.setCallback(function () {
            configure.changeMail();
            validate();
        }, '#mail-server-type');
        configure.changeMail();
        /* this assumes no other OnOff sliders on the initial setup page. */
        OnOff.setCallback(function (checked) {
            configure.changeSSL(checked);
            validate();
        }, '#enable-ssl');
        configure.setInputCallback(validate);
        /* no need to call validate(), the form can't be valid yet. */

        /* help */
        configure.lightbox(236535, 'Palette Server URL');
        configure.lightbox(237794, 'Tableau Server URL');
        configure.lightbox(237795, 'License Key');
        configure.lightbox(236536, 'Palette Admin Password');
        configure.lightbox(252063, 'Tableau Server Repository Database User Password');
        configure.lightbox(236542, 'Mail Server');
        configure.lightbox(236543, 'Server SSL Certificate');
        configure.lightbox(236544, 'Authentication');
        configure.lightbox(237785, 'Timezone');

        setupDone = true;
    }

    /*
     * queryLicensing()
     */
    function queryLicensing()
    {
        $.ajax({
            url: '/licensing',
            success: function(data) {
                $('div.error-page').addClass('hidden');
                $('div.setup-page').removeClass('hidden');
            },
            error: function (jqXHR, textStatus, errorThrown) {
                $('div.setup-page').addClass('hidden');
                $('div.error-page').removeClass('hidden');
                setTimeout(queryLicensing, LICENSE_TIMEOUT);
            }
        });
    }

    /* start */
    queryLicensing();

    $.ajax({
        url: '/open/setup',
        success: function(data) {
            $().ready(function() {
                setup(data);
            });
        },
        error: function (jqXHR, textStatus, errorThrown) {
            /* FIXME: do something... */
        }
    });
});
