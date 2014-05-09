# -*- coding: utf-8 -*-
<%inherit file="layout.mako" />

<%block name="title">
    <title>Palette - Manage</title>
</%block>

<section class="secondary-side-bar">
    <a class="Psmall-only" id="toggle-events" href="#"><i class="fa"></i></a>
    <h5>Tableau Server Application</h5>
    <h5 class="sub">123.123.1.1</h5>
    <h5 class="sub">Port 6577</h5>
    <ul class="actions">
        <li>
        	<a name="popupStart" class="popup-link"> 
        		<i class="fa fa-fw fa-play"></i>
        		<span>Start</span>
        	</a>
        </li>
        <li>
        	<a name="popupStop" class="popup-link"> 
        		<i class="fa fa-fw fa-stop"></i>
        		<span>Stop</span>
        	</a>
        </li>
        <li>
        	<a name="popupRestore" class="popup-link"> 
        		<i class="fa fa-fw fa-repeat"></i>
        		<span>Reset</span>
        	</a>
        </li>
        <li>
        	<a href="#"> 
        		<i class="fa fa-fw fa-power-off"></i>
        		<span>Restart Server</span>
        	</a>
        </li>
    </ul>
</section>

<%include file="events.mako" />

<article class="popup" id="popupStart">
    <section class="popup-body">
        <section class="row">
            <section class="col-xs-12">
                <p>Are you sure want to <span class="bold">start</span> the Tableau Server Application</p>
            </section>
        </section>
        <section class="row">
            <section class="col-xs-6">
                <button type="submit" name="save" class="p-btn p-btn-grey popup-close">Cancel</button>
            </section>
            <section class="col-xs-6">
                <button type="submit" name="save" class="p-btn p-btn-blue">Start</button>
            </section>
        </section>
    </section>
    <div class="shade">&nbsp;</div>
</article>

<article class="popup" id="popupStop">
    <section class="popup-body">
        <section class="row">
            <section class="col-xs-12">
                <p>Are you sure want to <span class="bold">stop</span> the Tableau Server Application</p>
            </section>
        </section>
        <section class="row">
            <section class="col-xs-6">
                <button type="submit" name="save" class="p-btn p-btn-grey popup-close">Cancel</button>
            </section>
            <section class="col-xs-6">
                <button type="submit" name="save" class="p-btn p-btn-blue">Stop</button>
            </section>
        </section>
    </section>
    <div class="shade">&nbsp;</div>
</article>

<article class="popup" id="popupRestore">
    <section class="popup-body">
        <section class="row">
            <section class="col-xs-12">
                <p>Are you sure want to <span class="bold">restore</span> the Tableau Server Application with backup from <span class="bold"> 12:00 AM on April 15, 2014</span>?</p>
            </section>
        </section>
        <section class="row">
            <section class="col-xs-12">
                <ul class="checkbox">
                    <li>
                        <input type="checkbox">
                        <label class="checkbox">
                            <span></span>
                            With configureation settings
                        </label>
                    </li>
                    <li>
                        <input type="checkbox">
                        <label class="checkbox">
                            <span></span>
                            With backup rollback protection
                        </label>
                    </li>
                </ul>
            </section>
        </section>
        <section class="row">
            <section class="col-xs-6">
                <button type="submit" name="save" class="p-btn p-btn-grey popup-close">Cancel</button>
            </section>
            <section class="col-xs-6">
                <button type="submit" name="save" class="p-btn p-btn-blue">Restore</button>
            </section>
        </section>
    </section>
    <div class="shade">&nbsp;</div>
</article>

<script src="/app/module/palette/js/vendor/require.js" data-main="/app/module/palette/js/common.js">
</script>
