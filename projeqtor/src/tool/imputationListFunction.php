<?php // ==============================================================================================================
      // =========================================== FUNTIONS ==========================================================
      // ==============================================================================================================


function drawDisplayFieldImputation() {
?>
 <table style="border:solid 1px lightgray;">
        <tr>
        <td colspan="2" style="padding-top:3px;padding-left:5px;padding-right:3px">
          <table style="width:100%;"><tr><td style="width:40px;"><div class="iconChangeLayout iconSize32 imageColorNewGui" style="border:0"></div></td><td class="dependencyHeader planningDialogTitle" style="text-align:left;"> &nbsp;&nbsp;<?php echo i18n('tabDisplay');?></td></tr></table>
        </td>
      </tr>
        
        <tr>
         <td colspan="2">
          <table>
              <tr>
                <td>
                  <?php drawOptionsDisplaySwitchImputation();?>
                </td>
              </tr>
          </table>
         </td>
        </tr>
     </table>
<?php 
}

function drawOptionsDisplaySwitchImputation() {
 global $displayOnlyCurrentWeekMeetings,$hideDone,$showPlanned,$hideNotHandled,$displayHandledGlobal,$showId,$hidePausedItem,$limitResourceByProj,$displayProjectColorImputation,$displayActivityColorImputation;
?>
  <table style="margin-left:20px;margin-top:10px;" width="100%">
    <tr title="<?php echo pq_ucfirst(i18n('meetingWeekOnly'));?>">
      <td style="padding-top:6px;">
        <div   id="listDisplayOnlyCurrentWeekMeetings" name="listDisplayOnlyCurrentWeekMeetings" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($displayOnlyCurrentWeekMeetings==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
               return refreshImputationList();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("meetingWeekOnly");?></td>
    </tr>
    
      <tr title="<?php echo pq_ucfirst(i18n('colShowClosedItems'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowIdle" name="listShowIdle" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (sessionValueExists('listShowIdleTimesheet') and getSessionValue('listShowIdleTimesheet')=='on') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
                 saveDataToSession("listShowIdleTimesheet",((this.value=='on')?'on':'off'),true);
                 return refreshImputationList();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("closeElement");?></td>
    </tr>
    
    
     <tr title="<?php echo pq_ucfirst(i18n('labelShowDone'));?>">
      <td style="padding-top:6px;">
        <div   id="listHideDone" name="listHideDone" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($hideDone==1) {echo 'value="off"'; }else{echo 'value="on"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
               return refreshImputationList();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("doneElement");?></td>
    </tr>
  
     <?php if ( $displayHandledGlobal!="YES") { ?>
    <tr title="<?php echo pq_ucfirst(i18n('notBeginelement'));?>">
      <td style="padding-top:6px;">
        <div   id="listHideNotHandled" name="listHideNotHandled" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($hideNotHandled==1) {echo 'value="off"'; }else{echo 'value="on"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
               return refreshImputationList();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("notBeginelement");?></td>
    </tr>
    <?php }?>

     <tr title="<?php echo pq_ucfirst(i18n('pauseElement'));?>">
      <td style="padding-top:6px;">
        <div   id="hidePausedItem" name="hidePausedItem" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (!$hidePausedItem) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
                saveDataToSession("hidePausedItem",((this.value=='on')?'on':'off'),true); 
                return refreshImputationList();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("pauseElement");?></td>
    </tr>
    
     <tr title="<?php echo pq_ucfirst(i18n('labelShowId'));?>">
      <td style="padding-top:6px;">
        <div   id="showId" name="showId" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($showId==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
               return refreshImputationList();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("colId");?></td>
    </tr>
    
     <tr title="<?php echo pq_ucfirst(i18n('labelShowPlannedWork'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowPlannedWork" name="listShowPlannedWork" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($showPlanned==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
               return refreshImputationList();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("plannedWork");?></td>
    </tr>
    
    <tr title="<?php echo pq_ucfirst(i18n('labelLimitResourceByProject'));?>">
      <td style="padding-top:6px;">
        <div   id="limitResByProj" name="limitResByProj" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($limitResourceByProj=='on') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
                saveDataToSession("limitResourceByProject",((this.value=='on')?'on':'off'),true); 
                refreshList('imputationResource', null, null, dijit.byId('userName').get('value'), 'userName', true);
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("resourceProjectSelected");?></td>
    </tr>
    
    <tr title="<?php echo pq_ucfirst(i18n('displayProjectColorTimesheet'));?>">
      <td style="padding-top:6px;">
        <div   id="listDisplayProjectColorImputation" name="listDisplayProjectColorImputation" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($displayProjectColorImputation==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>  
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
                return refreshImputationList();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("labelDisplayProjectColorTimesheet");?></td>
 
      <tr title="<?php echo pq_ucfirst(i18n('displayActivityColorTimesheet'));?>">
      <td style="padding-top:6px;">
        <div   id="listDisplayActivityColorImputation" name="listDisplayActivityColorImputation" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($displayActivityColorImputation==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>  
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
                return refreshImputationList();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"> <?php echo i18n("labelDisplayActivityColorTimesheet");?></td>
   </table>
<?php 
}

function drawDisplayFilterImputation(){
  global $displaySearchName;
?>
        
    <table style="border:solid 1px lightgray;width:100%;">
     <tr>
      <td colspan="2" style="padding-top:3px;padding-left:5px;padding-right:3px">
        <table style="width:100%;"><tr><td style="width:35px;"><div style="position:relative;left:2px;top:2px" class="dijitButtonIcon iconFilter iconSize32 imageColorNewGui"></div></td><td class="dependencyHeader planningDialogTitle" style="text-align:left;"> &nbsp;&nbsp;<?php echo pq_ucfirst(i18n('filters'));?></td></tr></table>
      </td>
    </tr>
       <tr>
        <td colspan="2">
          <table style="margin-left:5px;">
            <tr>
  <tr>
                  <td style="text-align:right;">
                    <span class="nobr"><?php echo i18n("colId")?>&nbsp;&nbsp;</span> 
                  </td>
                  <td>
                    <div title="<?php echo i18n('filterOnId')?>" style="max-width:100px;" class="filterField rounded" dojoType="dijit.form.TextBox" 
                          type="text" id="listIdFilterImp" name="listIdFilterImp" value="<?php if(sessionValueExists('listIdFilterImp')){ echo getSessionValue('listIdFilterImp'); }?>">
                      <script type="dojo/method" event="onKeyUp" >
                        dijit.byId('listNameFilterImp').set('value','');
                        if(dijit.byId('listIdFilterImpDisplay')){
                          if(dijit.byId('listIdFilterImpDisplay').get('value') != dijit.byId('listIdFilterImp').get('value')){
                            dijit.byId('listIdFilterImpDisplay').set('value',dijit.byId('listIdFilterImp').get('value'));
                          }
                        }
                        dijit.byId("listIdFilterImpDisplay").domNode.style.display = 'block';
                        dojo.byId("listIdFilterImpDisplayId").style.display='';
                        setTimeout("filterByIdTimesheet(dijit.byId('listIdFilterImp').get('value'),1)",500);
                        dijit.byId("listNameFilterImpDisplay").domNode.style.display = 'none';
                        dojo.byId("listNameFilterImpDisplayId").style.display='none';
                      </script>
                    </div>
                  </td>   
                </tr>
                
                <tr> 
                  <td style="text-align:right;">
                    <span class="nobr"><?php echo i18n("colName");?>&nbsp;<?php if (!isNewGui()) echo ':';?>&nbsp;</span> 
                  </td>
                  <td>
                    <div title="<?php echo i18n('filterOnName')?>" style="width:200px" type="text" class="filterField rounded" dojoType="dijit.form.TextBox" 
                        id="listNameFilterImp" name="listNameFilterImp"  value="<?php if(sessionValueExists('listNameFilterImp')){ echo getSessionValue('listNameFilterImp'); }?>">
                      <script type="dojo/method" event="onKeyUp" >
                        dijit.byId('listIdFilterImp').set('value','');
                        if(dijit.byId('listNameFilterImpDisplay')){
                          if(dijit.byId('listNameFilterImpDisplay').get('value') != dijit.byId('listNameFilterImp').get('value')){
                            dijit.byId('listNameFilterImpDisplay').set('value',dijit.byId('listNameFilterImp').get('value'));
                          }
                        }
                        dijit.byId("listNameFilterImpDisplay").domNode.style.display = 'block';
                        dojo.byId("listNameFilterImpDisplayId").style.display='';
                        if(dijit.byId("imputationSearchOnName")) {
                          var currentSwitchValue = dijit.byId("imputationSearchOnName").get('value');
                          if(currentSwitchValue != "on") {
                            dijit.byId("imputationSearchOnName").set('value', 'on');
                            saveUserParameter("imputationSearchOnName", "on", true);
                          }
                        }
                        setTimeout("filterByIdTimesheet(dijit.byId('listNameFilterImp').get('value'),0)",500);
                        dijit.byId("listIdFilterImpDisplay").domNode.style.display = 'none';
                        dojo.byId("listIdFilterImpDisplayId").style.display='none';
                      </script>
                    </div>
                  </td>
                  <?php 
                    $displaySearchName = Parameter::getUserParameter('imputationSearchOnName');
                    $searchOnName = (Parameter::getGlobalParameter('imputationSearchOnName')=="YES")? true : false;
                    $searchOnName = ($displaySearchName == 'on' or ($searchOnName==true and $displaySearchName != 'off'))? true :false;
                  ?>
                  <td style="padding:18px 5px 0 5px;">
                    <div id="imputationSearchOnName" name="imputationSearchOnName" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                    <?php if ($searchOnName==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>
                    leftLabel="" rightLabel="" style="width:25px;" >
                        <script type="dojo/method" event="onStateChanged" >
                          if(this.value == "on") {
                            saveUserParameter("imputationSearchOnName", this.value, true);
                            if(dijit.byId("listNameFilterImpDisplay")) {
                              dijit.byId("listNameFilterImpDisplay").domNode.style.display = 'block';
                            }
                            if(dojo.byId("listNameFilterImpDisplayId")) {
                              dojo.byId("listNameFilterImpDisplayId").style.display = '';
                            }
                          } else {
                            saveUserParameter("imputationSearchOnName", this.value, false);
                            if(dijit.byId("listNameFilterImpDisplay")) {
                              dijit.byId("listNameFilterImpDisplay").domNode.style.display = 'none';
                            }
                            if(dojo.byId("listNameFilterImpDisplayId")) {
                              dojo.byId("listNameFilterImpDisplayId").style.display = 'none';
                            }
                          }
                      </script>
              		  </div>&nbsp;
                  </td>
                  
                </tr>
              </tr>
            <tr>
            </tr>
          </table>
        </td>
      </tr>
  </table>
<?php 
}


function drawExportsImputation() {
?>
<table style="border:solid 1px lightgray;width:100%;">
     <tr>
      <td colspan="2" style="padding-top:3px;padding-left:5px;padding-right:3px">
        <table style="width:100%;"><tr><td style="width:35px;"><div style="position:relative;left:-2px;top:-2px" class="iconExport iconSize32 imageColorNewGui"></div></td><td class="dependencyHeader planningDialogTitle" style="text-align:left;"> &nbsp;&nbsp;<?php echo i18n('tabExport');?></td></tr></table>
      </td>
    </tr>
    <tr>
      <td colspan="2">
        <table style="width:100%;">
          <tr>
            <td style="width:40px">&nbsp;</td>
            <td style="width:100px;text-align:center;padding:5px;padding-top:0;vertical-align:top">
                <button title="<?php echo i18n('print')?>"
                 dojoType="dijit.form.Button"
                 id="printButton" name="printButton"
                 iconClass="iconButton imageColorNewGui iconPrint iconSize32" class="buttonIconNewGui detailButton" showLabel="false">
                  <script type="dojo/connect" event="onClick" args="evt">
                  showPrint('../report/imputation.php', 'imputation');
                  </script>
                </button>
                <div style="xfont-style:italic;font-size:80%;color:#a0a0a0"><?php echo i18n('planningPrint');?></div>
            </td>
            <td style="width:100px;text-align:center;padding:5px;padding-top:0;vertical-align:top">
                <button title="<?php echo i18n('reportPrintPdf')?>"
                  dojoType="dijit.form.Button"
                  id="printButtonPdf" name="printButtonPdf"
                  iconClass="iconButton imageColorNewGui iconButtonPdf iconSize32" class="buttonIconNewGui detailButton" showLabel="false">
                  <script type="dojo/connect" event="onClick" args="evt">
                    showPrint('../report/imputation.php', 'imputation', null, 'pdf');
                  </script>
                </button>
                <div style="xfont-style:italic;font-size:80%;color:#a0a0a0"><?php echo i18n('planningPDF');?></div>
            </td>
            <td style="width:100px;text-align:center;padding:5px;padding-top:0;vertical-align:top">
                 <button title="<?php echo i18n('reportPrintCsv')?>"
                  dojoType="dijit.form.Button"
                  id="listPrintCsv2" name="listPrintCsv2"
                  iconClass="iconButton imageColorNewGui iconButtonCsv iconSize32" class="buttonIconNewGui detailButton" showLabel="false">
                  <script type="dojo/connect" event="onClick" args="evt">
                   openExportDialog('csv');
                  </script>
                </button>
                <div style="xfont-style:italic;font-size:80%;color:#a0a0a0"><?php echo i18n('planningCSV');?></div>
            </td>
          </tr>
          <tr><td colspan="4" style="text-align:right;">
            <table style="float:right;"><tr>
                                  <?php
              $extraPlgButtons=Plugin::getButtons('extra', 'Imputation');
              foreach ($extraPlgButtons as $bt) { ?>
                <td style="width:100px;text-align:center;padding:5px;padding-top:0;vertical-align:top">
                <button id="pluginButtonList<?php echo $bt->id;?>" dojoType="dijit.form.Button" showlabel="false"
                  title="<?php echo i18n($bt->buttonName);?>"
                  iconClass="<?php echo $bt->iconClass;?>" class="detailButton">
                  <script type="dojo/connect" event="onClick" args="evt">
                  <?php if ($bt->scriptJS) {
                          echo $bt->scriptJS;
                        } else { ?>
                          var periodType=dojo.byId('rangeType').value;
                          var period=dojo.byId('rangeValue').value;
                          var idResource=dijit.byId('userName').get("value");
                          loadContent("<?php echo $bt->scriptPHP;?>"+"?rangeType="+periodType+"&period="+period+"&resource="+idResource, "resultDivMain", "listForm", true);
                  <?php }?>
                  </script>
                </button>
                <div style="xfont-style:italic;font-size:80%;color:#a0a0a0"><?php echo i18n($bt->buttonName);?></div>
                <td>
              <?php }?>
              
              </tr></table>
          </td></tr>  
        </table>
      </td>
    </tr>
  </table>
<?php 
}

?>