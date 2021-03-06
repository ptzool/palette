# -*- coding: utf-8 -*-
<div class="content">
  <div>
    <div class="top-zone">
      <%include file="paging.mako" args="name='Events'" />
      <h1>Events</h1>
      <div class="filter-dropdowns">
        <div id="status-dropdown" class="btn-group"></div>
        <div id="type-dropdown" class="btn-group"></div>
      </div> <!-- filter-dropdowns -->
    </div> <!-- top-zone -->
    <div class="bottom-zone">
      <section id="event-list"></section>
      <%include file="paging.mako" args="name='Events'" />
    </div> <!-- bottom-zone -->

    <script id="event-list-template" type="x-tmpl-mustache">
      {{#events}}
      <article class="item" id="item{{eventid}}">
        <div class="summary clearfix" data-toggle="item">
          <span class="fa-stack">
            <i class="fa fa-circle fa-stack-1x"></i>
            <i class="fa fa-fw fa-stack-1x {{icon}} {{color}}"></i>
          </span>
          <div>
            <h3>{{title}}</h3>
            <p>{{summary}}</p>
          </div>
          <i class="expand"></i>
        </div>
        <div class="description">{{{description}}}</div>
      </article>
      {{/events}}
    </script>
  </div>
</div> <!-- content -->
