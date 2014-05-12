<section class="dynamic-content">
  <section class="top-zone">
    <section class="row">
      <section class="col-xs-12">
        <h1 class="page-title">Events</h1>
<!--
        <a href="#" class="alert errors"><span>0</span></a>
        <a href="#" class="alert warnings"><span>0</span></a>
-->
        <a class="Psmallish-only" id="toggle-event-filters" href="#"><i class="fa fa-angle-left"></i></a>
      </section>
    </section>
    <section class="row">
      <section class="col-xs-12">
        <div class="btn-group">
          <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><div>All Status</div><span class="caret"></span>
          </button>
          <ul class="dropdown-menu" role="menu">
            <li><a href="#">All Statuses</a></li>
            <li><a href="#">Success</a></li>
            <li><a href="#">Warning</a></li>
            <li><a href="#">Error</a></li>
          </ul>
        </div>
        <div class="btn-group">
          <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><div>All Sites</div><span class="caret"></span>
          </button>
          <ul class="dropdown-menu" role="menu">
            <li><a href="#">All Sites</a></li>
            <li><a href="#">Finance</a></li>
            <li><a href="#">Marketing</a></li>
          </ul>
        </div>
        <div class="btn-group">
          <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><div>All Types</div><span class="caret"></span>
          </button>
          <ul class="dropdown-menu" role="menu">
            <li><a href="#">All Types</a></li>
            <li><a href="#">Application</a></li>
            <li><a href="#">Communication</a></li>
            <li><a href="#">Extract</a></li>
            <li><a href="#">System</a></li>
          </ul>
        </div>
        <div class="btn-group pull-right">
          <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><i class="fa fa-fw fa-calendar"></i> Select Date<span class="caret"></span>
          </button>
          <ul class="dropdown-menu" role="menu">
            <li><a href="#">1 Week ago</a></li>
            <li><a href="#">2 Weeks ago</a></li>
            <li><a href="#">1 Month ago</a></li>
            <li><a href="#">2 Months ago</a></li>
            <li><a href="#">3 Months ago</a></li>
            <li><a href="#">6 Months ago</a></li>
          </ul>
        </div>
      </section>
    </section>
  </section>
  <section class="bottom-zone">
    <section class="col-lg-12" id="event-list"></section>
  </section>
</section>

<script id="event-list-template" type="x-tmpl-mustache">
  {{#events}}
  <article class="event">
    <i class="fa fa-fw fa-hdd-o {{color}}"></i>
    <h3>{{title}}</h3>
    <p>{{summary}}</p>
    <div>{{{description}}}</p>
  </article>
  {{/events}}
</script>
