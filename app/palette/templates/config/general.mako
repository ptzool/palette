# -*- coding: utf-8 -*-
<%inherit file="../webapp.mako" />

<%block name="title">
<title>Palette - General Configuration</title>
</%block>

<div class="content general-page">
  <div>
    <div class="top-zone">
      <h1>General Configuration</h1>
    </div> <!-- top-zone -->

    <div class="bottom-zone">
      <a name="storage"></a>
      <section class="form-group" id="storage">
        <a id="229204" data-toggle="help" href="#"><i class="help"></i></a>
        <h2>Storage Location</h2>
        <p>Your Backups, Ziplogs, and Workbooks will be saved in this location.</p>
        <div> <!-- class="radio -->
          <input type="radio" id="storage-local" name="storage-type" value="local" />
          <label for="storage-local">My Machine(s)</label>
          <input type="radio" id="storage-s3" name="storage-type" value="s3" />
          <label for="storage-s3">Amazon S3</label>
          <input type="radio" id="storage-gcs" name="storage-type" value="gcs" />
          <label for="storage-gcs">Google Cloud Storage</label>
        </div>
        <section id="local" class="hidden">
          <span class="btn-group" id="storage-destination"></span>
          <div class="save-cancel">
            <button type="button" id="cancel-local" class="cancel disabled">
              Cancel
            </button>
            <button type="button" id="save-local" class="save disabled">
              Save
            </button>
          </div>
        </section>
        <section id="s3" class="hidden">
          <h3>Credentials</h3>
          <label class="control-label" for="s3-access-key">Access Key ID</label>
          <input class="form-control" type="text" id="s3-access-key" />
          <label class="control-label" for="s3-secret-key">Secret Access Key</label>
          <input class="form-control" type="password" id="s3-secret-key" />
          <label class="control-label" for="s3-url">S3 URL or Bucket Name</label>
          <input class="form-control" type="text" id="s3-url" />
          <div class="btn-bar">
            <button type="button" id="test-s3" class="btn-test">
              Test Connection
            </button>
            <button type="button" id="remove-s3" class="btn-test">
              Remove Credentials
            </button>
          </div>
          <p id="s3-test-message" class="hidden"></p>
          <div class="save-cancel">
            <button type="button" id="cancel-s3" class="cancel disabled">
              Cancel
            </button>
            <button type="button" id="save-s3" class="save disabled">
              Save
            </button>
          </div>
        </section>
        <section id="gcs" class="hidden">
          <h3>Credentials</h3>
          <label class="control-label" for="gcs-access-key">Access Key ID</label>
          <input class="form-control" type="text" id="gcs-access-key" />
          <label class="control-label" for="gcs-secret-key">Secret Access Key</label>
          <input class="form-control" type="password" id="gcs-secret-key" />
          <label class="control-label" for="gcs-url">GCS URL or Bucket Name</label>
          <input class="form-control" type="text" id="gcs-url" />
          <div class="btn-bar">
            <button type="button" id="test-gcs" class="btn-test">
              Test Connection
            </button>
            <button type="button" id="remove-gcs" class="btn-test">
              Remove Credentials
            </button>
          </div>
          <p id="gcs-test-message" class="hidden"></p>
          <div class="save-cancel">
            <button type="button" id="cancel-gcs" class="cancel disabled">
              Cancel
            </button>
            <button type="button" id="save-gcs" class="save disabled">
              Save
            </button>
          </div>
        </section>
      </section>  <!-- section storage -->

      <a name="email-alerts"></a>
      <hr />
      <section class="form-group" id="email-alerts">
        <a id="229207" data-toggle="help" href="#"><i class="help"></i></a>
        <h2>Email Alerts</h2>
        <p>Designate which groups of Palette Users receive Email Alerts.</p>
        <div class="slider-group">
          <div>
            <div>Alerts to Palette Admins</div>
            <span id="alert-admins" class="onoffswitch yesno"></span>
          </div>
          <div>
            <div>Alerts to Publishers</div>
            <span id="alert-publishers" class="onoffswitch yesno"></span>
          </div>
        </div>

        <div class="save-cancel">
          <button type="button" id="cancel-email-alerts" class="cancel disabled">
            Cancel
          </button>
          <button type="button" id="save-email-alerts" class="save disabled">
            Save
          </button>
        </div>
      </section> <!-- section email alerts -->

      <a name="backups"></a>
      <hr />
      <section class="form-group" id="backups">
        <a id="229213" data-toggle="help" href="#"><i class="help"></i></a>
        <h2>Backups</h2>
        <!---
            <p class="slider-group">
              <span>Scheduled Backups
                <span id="scheduled-backups" class="onoffswitch yesno"></span>
              </span>
            </p>
            -->
        <h3>Scheduled Backups</h3>
        <p>The number of scheduled Backups you want Palette to keep in storage.</p>
        <p><span id="backup-auto-retain-count" class="btn-group count"></span> Backups</p>
        <!--
            <h3>Frequency and Time of Scheduled Backups</h3>
            <p>
              <span>Run Backup Every
                <span id="scheduled-backup-period" class="btn-group percentage"></span> Hours</span>
              &nbsp;<span>Starting at <span id="scheduled-backup-hour" class="btn-group percentage"></span> : <span id="scheduled-backup-minute" class="btn-group percentage"></span> : <span id="scheduled-backup-ampm" class="btn-group ampm"></span>
                <span class="timezone"></span></span>
            </p>
            -->
        <h3>User Requested Backups</h3>
        <p>The number of user requested Backups you want Palette to keep in storage.</p>
        <p>
          <span id="backup-user-retain-count" class="btn-group count"></span> Backups
        </p>
        <div class="save-cancel">
          <button type="button" id="cancel-backups" class="cancel disabled">
            Cancel
          </button>
          <button type="button" id="save-backups" class="save disabled">
            Save
          </button>
        </div>
      </section> <!-- section backups -->

      <a name="ziplogs"></a>
      <hr />
      <section class="form-group" id="ziplogs">
        <a id="229214" data-toggle="help" href="#"><i class="help"></i></a>
        <h2>Ziplogs</h2>
        <!--
            <p class="slider-group">
              <span>Scheduled Ziplogs
                <span id="scheduled-ziplogs" class="onoffswitch yesno"></span>
              </span>
            </p>
            -->
        <h3>Scheduled Ziplogs</h3>
        <p>The number of scheduled Ziplogs you want Palette to keep in storage.</p>
        <p>
          <span id="ziplog-auto-retain-count" class="btn-group count"></span> Ziplogs
        </p>
        <h3>User Requested Ziplogs</h3>
        <p>The number of user requested Ziplogs you want Palette to keep in storage.</p>
        <p>
          <span id="ziplog-user-retain-count" class="btn-group count"></span> Ziplogs
        </p>
        <div class="save-cancel">
          <button type="button" id="cancel-ziplogs" class="cancel disabled">
            Cancel
          </button>
          <button type="button" id="save-ziplogs" class="save disabled">
            Save
          </button>
        </div>
      </section> <!-- section ziplogs -->

      <a name="extracts"></a>
      <hr />
      <section class="form-group auto" id="extracts">
        <a id="332776" data-toggle="help" href="#"><i class="help"></i></a>
        <h2>Extracts</h2>

        <h3>Delayed Extracts</h3>
        <p>Alert when scheduled extracts do not start before these duration thresholds.</p>
        <p>
          <span>Warning Alert at <span id="extract-delay-warn" class="btn-group time"></span></span>&nbsp;<span>Error Alert at <span id="extract-delay-error" class="btn-group time"></span></span>
        </p>
        <h3>Long-Running Extracts</h3>
        <p>Alert when extracts take longer to run than these duration thresholds.</p>
        <p>
          <span>Warning Alert at <span id="extract-duration-warn" class="btn-group time"></span></span>&nbsp;<span>Error Alert at <span id="extract-duration-error" class="btn-group time"></span></span>
        </p>
        <div class="save-cancel">
          <button type="button" class="cancel disabled">
            Cancel
          </button>
          <button type="button" class="save disabled">
            Save
          </button>
        </div>
      </section> <!-- section extracts -->

      <a name="archives"></a>
      <hr />
      <section class="form-group auto" id="archives">
        <a id="229215" data-toggle="help" href="#"><i class="help"></i></a>
        <h2>Archiving</h2>
        <p>Designate what Palette Server should archive.</p>
        <div class="slider-group">
          <div>
            <div>Archive Workbooks</div>
            <span id="workbook-archive-enabled" class="onoffswitch"></span>
          </div>
          <div>
            <div>Archive Data Sources</div>
            <span id="datasource-archive-enabled" class="onoffswitch"></span>
          </div>
        </div>
        <div class="settings hidden">
          <div class="workbooks">
            <p>The number of user Worbook Versions you want Palette to retain</p>
            <p>
              <span id="workbook-retain-count" class="btn-group count"></span> Workbook Versions
            </p>
          </div>
          <div class="datasources">
            <p>The number of user Datasource Versions you want Palette to retain</p>
            <p>
              <span id="datasource-retain-count" class="btn-group count"></span> Datasource Versions
            </p>
          </div>
          <label class="control-label required" for="archive-username">Tableau Server Admin Username</label>
          <input class="form-control" type="text" id="archive-username" />
          <label class="control-label required" for="archive-password">Tableau Server Admin Password</label>
          <input class="form-control" type="password" id="archive-password" />
        </div>
        <div class="save-cancel">
          <button type="button" id="cancel-archives" class="cancel disabled">
            Cancel
          </button>
          <button type="button" id="save-archives" class="save disabled">
            Save
          </button>
        </div>
      </section> <!-- section archives -->

      <a name="monitoring"></a>
      <hr />
      <section class="form-group" id="monitoring">
        <a id="229216" data-toggle="help" href="#"><i class="help"></i></a>
        <h2>Monitoring</h2>

        <div>
          <h3>Storage</h3>
          <p>Alert when my Machine attached volumes exceed these thresholds.</p>
          <p>
            <span>Warning Alert at <span id="disk-watermark-low" class="btn-group percentage"></span></span>&nbsp;<span>Error Alert at <span id="disk-watermark-high" class="btn-group percentage"></span></span>
          </p>
        </div>
        <div>
          <h3>CPU</h3>
          <p>Alert when the average CPU of my Machine(s) exceeds these thresholds for this duration.</p>
          <p>
            <span>Warning Alert at <span id="cpu-load-warn" class="btn-group percentage"></span></span>&nbsp;<span>for <span id="cpu-period-warn" class="btn-group time"></span></span>
          </p>
          <p>
            <span>Error Alert at <span id="cpu-load-error" class="btn-group percentage"></span></span>&nbsp;<span>for <span id="cpu-period-error" class="btn-group time"></span></span>
          </p>
        </div>
        <div>
          <h3>Workbook</h3>
          <p>Alert when workbook web view Page Load Times exceed these thresholds.</p>
          <p>
            Warning Alert at <span id="http-load-warn" class="btn-group percentage up"></span>&nbsp;Error Alert at <span id="http-load-error" class="btn-group percentage up"></span>
          </p>
        </div>
        <div class="save-cancel">
          <button type="button" id="cancel-monitors" class="cancel disabled">
            Cancel
          </button>
          <button type="button" id="save-monitors" class="save disabled">
            Save
          </button>
        </div>
      </section> <!-- section monitoring -->
    </div> <!-- bottom-zone -->
  </div>
</div> <!-- content -->

<script src="/js/vendor/require.js" data-main="/js/general.js">
</script>
