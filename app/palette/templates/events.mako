<section class="top-zone">
  <section class="row">
    <section class="col-xs-12">
      <h1 class="page-title">Events</h1>
      <div class="pagenav">
        <div class="count"><span>0</span> Events</div>
        <span class="first">
          <a href="#"><i class="fa fa-angle-double-left"></i></a>&nbsp;
        </span>
        <span class="previous">
          <a href="#"><i class="fa fa-angle-left"></i></a>
        </span>
	    <div class="numbering">
	      &nbsp;Page <span class="page-number"></span> of <span class="page-count"></span>
	    </div>
        <span class="next">
          <a href="#"><i class="fa fa-angle-right"></i></a>&nbsp;
        </span>
        <span class="last">
          <a href="#"><i class="fa fa-angle-double-right"></i></a>
        </span>
      </div>
    </section>
  </section>
  <section class="row">
    <section class="col-xs-12 filter-dropdowns">
      <div id="status-dropdown" class="btn-group"></div>
      <div id="type-dropdown" class="btn-group"></div>
    </section>
  </section>
</section>
<section class="bottom-zone">
  <section id="event-list"></section>
  <div class="pagenav">
    <span class="first">
      <a href="#"><i class="fa fa-angle-double-left"></i></a>&nbsp;
    </span>
    <span class="previous">
      <a href="#"><i class="fa fa-angle-left"></i></a>
    </span>
	<div class="numbering">
	  &nbsp;Page <span class="page-number"></span> of <span class="page-count"></span>
	</div>
    <span class="next">
      <a href="#"><i class="fa fa-angle-right"></i></a>&nbsp;
    </span>
    <span class="last">
      <a href="#"><i class="fa fa-angle-double-right"></i></a>
    </span>
  </div>
</section>

<script id="event-list-template" type="x-tmpl-mustache">
  {{#events}}
  <article class="event">
    <div class="summary clearfix">
      <span class="fa-stack">
	<i class="fa fa-circle fa-stack-2x"></i>
	<i class="fa fa-fw {{icon}} {{color}}"></i>
      </span>
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

<script id="event-dropdown-template" type="x-tmpl-mustache">
  <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><div data-id="{{id}}">{{value}}</div><span class="caret"></span>
  </button>
  <ul class="dropdown-menu" role="menu">
    {{#options}}
    <li><a data-id="{{id}}">{{item}}</a></li>
    {{/options}}
  </ul>
</script>
