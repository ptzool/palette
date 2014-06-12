<section class="top-zone">
  <section class="row">
    <section class="col-xs-12">
      <h1 class="page-title">Events</h1>
      <!--
          <a href="#" class="alert errors"><span>0</span></a>
          <a href="#" class="alert warnings"><span>0</span></a>
	  -->
    </section>
  </section>
  <section class="row">
    <section class="col-xs-12 nowrap">
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
        <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><div>All Publishers</div><span class="caret"></span>
        </button>
        <ul class="dropdown-menu" role="menu">
          <li><a href="#">All Publishers</a></li>
          <li><a href="#">John Abdo</a></li>
          <li><a href="#">Matthew Laue</a></li>
        </ul>
      </div>
      <div class="btn-group">
        <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><div>All Projects</div><span class="caret"></span>
        </button>
        <ul class="dropdown-menu" role="menu">
          <li><a href="#">All Projects</a></li>
          <li><a href="#">Quarterly Reports</a></li>
          <li><a href="#">Annual Reports</a></li>
        </ul>
      </div>

      <!-- TODO: Add back in Alpha 2 or later
      <div class="col-xs-4">
         <input class="form-control" type="text" placeholder="Workbook" style="margin-top:10px;">
      </div>
      -->

    </section>
  </section>
</section>
<section class="bottom-zone">
  <section id="event-list"></section>
</section>

<script id="event-list-template" type="x-tmpl-mustache">
  {{#events}}
  <article class="event">
    <div class="summary clearfix">
      <i class="fa fa-fw fa-hdd-o {{color}}"></i>
      <div>
	<h3>{{title}}</h3>
	<p>{{summary}}</p>
      </div>
      <i class="fa fa-fw fa-angle-down expand"></i>
    </div>
    <div class="description">{{{description}}}</div>
  </article>
  {{/events}}
</script>
