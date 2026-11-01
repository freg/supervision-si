<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU Affero General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/*
 * ============================================================================
 * List of parameter specific to a user.
 * Every user may change these parameters (for his own user only !).
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/view/today.php');
$user=getSessionUser();
$profile=new Profile($user->idProfile);
$cptMax=Parameter::getUserParameter('maxItemsInTodayLists');
if (!$cptMax) {
  $cptMax=100;
}

SqlElement::$_cachedQuery['Project']=array();
SqlElement::$_cachedQuery['ProjectPlanningElement']=array();
SqlElement::$_cachedQuery['PlanningElement']=array();

$templateProjectList=Project::getTemplateList();

$collapsedList=Collapsed::getCollaspedList();

$pe=new ProjectPlanningElement();
$pe->setVisibility();
$workVisibility=$pe->_workVisibility;
$costVisibility=$pe->_costVisibility;

$displayWidth=RequestHandler::getValue('destinationWidth');
$displayHeigth=RequestHandler::getValue('destinationHeight');
// $twoCols=($displayWidth>1400)?true:false;
// if (!isNewGui() ) $twoCols=false;
//$twoCols=false;
//echo "width=$displayWidth";

$arrayCols=array('Ticket', 'Activity', 'Milestone', 'Action', 'Risk', 'Issue', 'Question', 'Requirement','Delivery','SubTask');
$showCol=array();
foreach ($arrayCols as $col) {
  $prjVisLst=$user->getVisibleProjects();
  $crit='idProject in '.transformListIntoInClause($prjVisLst);
  if ($col=='Action') $crit.=' and '.SqlElement::getPrivacyClause();
  $obj=new $col();
  $cptCol[$col]=$obj->countGroupedSqlElementsFromCriteria(null, array('idProject', 'done', 'idle'), $crit);
  $showCol[$col]=securityCheckDisplayMenu(null, $col);
}

if (pq_array_key_exists('refreshProjects', $_REQUEST)) {
  setSessionValue('todayCountScope', (pq_array_key_exists('countScope', $_REQUEST))?$_REQUEST['countScope']:'todo');
  showProjectsOld();
  exit;
}
if(pq_array_key_exists('refreshMessage', $_REQUEST)) {
  showMessagesOld();
  exit;
}
if(pq_array_key_exists('refreshWorkDiv', $_REQUEST)) {
  showAssignedTasksOld();
  exit;
}
if(pq_array_key_exists('refreshRespDiv', $_REQUEST)) {
  showResponsibleTasksOld();
  exit;
}
if(pq_array_key_exists('refreshFollowDiv', $_REQUEST)) {
  showIssuerRequestorTasksOld();
  exit;
}
if(pq_array_key_exists('refreshDocumentDiv', $_REQUEST)) {
  //showDocumentsOld();
  showApproversOld();
  exit;
}
if(pq_array_key_exists('refreshTodoList', $_REQUEST)) {
  showSubTask();
  exit;
}

$today=new Today();
$crit=array('idUser'=>$user->id, 'idle'=>'0');
$todayList=$today->getSqlElementsFromCriteria($crit, false, null, 'sortOrder asc');
$asTodayProject=$today->getSingleSqlElementFromCriteria(get_class($today), array('scope'=>'static','staticSection'=>'Projects','idUser'=>$user->id, 'idle'=>'0'));
// initialize if empty
if (count($todayList)==0) {
  Today::insertStaticItems();
  $todayList=$today->getSqlElementsFromCriteria($crit, false, null, 'sortOrder asc');
  $asTodayProject=$today->getSingleSqlElementFromCriteria(get_class($today), array('scope'=>'static','staticSection'=>'Projects','idUser'=>$user->id, 'idle'=>'0'));
}
$print=false;
if (isset($_REQUEST['print'])) {
  $print=true;
}
$paramRefreshDelay=Parameter::getUserParameter('todayRefreshDelay');
if (!$paramRefreshDelay) $paramRefreshDelay=5;
$paramScrollDelay=Parameter::getUserParameter('todayScrollDelay');
if (!$paramScrollDelay) $paramScrollDelay=10;
$showActStream='false';
if(Parameter::getUserParameter('showTodayActivityStream')){
  $showActStream=Parameter::getUserParameter('showTodayActivityStream');
}
$topDivHeight="20%";
if($showActStream=='false'){
  $classicViewWidth=($displayWidth-20)*0.75.'px';
  $activityStreamWidth=($displayWidth-20)*0.25.'px';
}else{
  $classicViewWidth=($displayWidth-20).'px';
  $activityStreamWidth='0px';
} 
// $classicViewHeight='80%';
// $activityStreamHeight='80%';
$widthForDisplay=($displayWidth-20)*0.25;

if(getContentPaneSize('contentPaneTodayTopHeight')){
  $topDivHeight=getContentPaneSize('contentPaneTodayTopHeight').'px';
}
// if(getContentPaneSize('contentPaneTodayClassicViewHeight')){
//   $classicViewHeight=getContentPaneSize('contentPaneTodayClassicViewHeight').'px';
// }
// if(getContentPaneSize('contentPaneTodayActStreamHeight')){
//   $activityStreamHeight=getContentPaneSize('contentPaneTodayActStreamHeight').'px';
// }
$topDivHeightNum=intval(pq_substr($topDivHeight,0,pq_strlen($topDivHeight)-2));
if(($displayHeigth-30) <= $topDivHeightNum){
  $topDivHeight=$displayHeigth*0.9;
  $topDivHeight=$topDivHeight.'px';
}


if($showActStream=='false'){
  if(getContentPaneSize('contentPaneTodayActStreamWidth')){
    $widthForDisplay=getContentPaneSize('contentPaneTodayActStreamWidth');
    $activityStreamWidth=getContentPaneSize('contentPaneTodayActStreamWidth').'px';
  }
  if(getContentPaneSize('contentPaneTodayClassicViewWidth')){
    $classicViewWidth=(getContentPaneSize('contentPaneTodayClassicViewWidth')-30).'px';
    if(getContentPaneSize('contentPaneTodayClassicViewWidth')>= ($displayWidth-20)){
      $classicViewWidth=(($displayWidth-20)-$widthForDisplay);
    }
  }
}
$isModuleActive=true;
$menu =new Menu(177);
if (!Module::isMenuActive($menu->name))  $isModuleActive=false;
if (!securityCheckDisplayMenu($menu->id,pq_substr($menu->name,4)))$isModuleActive=false;



?>

<input type="hidden" name="objectClassManual" id="objectClassManual" value="Today" />
<div class="container" dojoType="dijit.layout.BorderContainer">
  <div style="overflow: <?php echo(!$print)?'auto':'hidden';?>;<?php if(!$isModuleActive)echo 'padding:10px;'; ?>" id="detailDiv" dojoType="dijit.layout.ContentPane" region="center">
     <?php 
    if (!$print) {?>
     <?php if($isModuleActive){?> 
    <div class="container" dojoType="dijit.layout.BorderContainer" liveSplitters="false"  > 
    <?php   if($asTodayProject->id!=''){?>
      <div dojoType="dijit.layout.ContentPane" id="todayTop" region="top" style="width:100%;height:<?php echo $topDivHeight;?> !important; padding-left:15px;padding-right:15px;" splitter="true" >
        <script type="dojo/connect" event="resize" args="evt">
          saveContentPaneResizing("contentPaneTodayTopHeight", dojo.byId("todayTop").offsetHeight, true);
        </script>
    <?php   }else{ ?>
   
      <div dojoType="dijit.layout.ContentPane" region="left" style="width:<?php echo  $classicViewWidth;?>; padding:15px;" splitter="true" id="todayClassicView" >
       <script type="dojo/connect" event="resize" args="evt">
         saveContentPaneResizing("contentPaneTodayClassicViewWidth", dojo.byId("todayClassicView").offsetWidth, true);
       </script>
  <?php      }
              }?>
      <div class="parametersButton">
        <button id="todayRefreshButton" dojoType="dijit.form.Button"
         showlabel="false" title="<?php echo i18n('enableRefresh');?>"
         style="width: 28px" class="detailButton"
          iconClass="dijitButtonIcon dijitButtonIconRefresh">
         <script type="dojo/connect" event="onClick" args="evt">
          if(typeof refreshEnabled === 'undefined') {
            if(dojo.byId('isMenuLeftOpen').value=='true')dojo.byId( 'hideStreamNewGui' ).click();
            enterFullScreen();
            if (menuActualStatus == 'visible' || !menuHidden) {
              hideShowMenu(false);
           }
           if (dojo.byId('menuBarShow')) dojo.byId('menuBarShow').style.top='0px';
           if (dojo.byId('statusBarDiv')) dojo.byId('statusBarDiv').style.top='-4px';
            if (dojo.byId('centerDiv')) {
             dojo.byId('centerDiv').style.top='0px';
             var heightCenterDiv = dojo.byId('centerDiv').style.height;
             heightCenterDiv = heightCenterDiv.substring(0,heightCenterDiv.length-2);
             heightCenterDiv =  parseInt(heightCenterDiv)+82;
             dijit.byId("centerDiv").resize({h :heightCenterDiv});
           }
           if (dijit.byId("toolBarDiv")) dijit.byId("toolBarDiv").resize({h :0});
           if (dijit.byId("statusBarDiv"))  dijit.byId("statusBarDiv").resize({h :0});
           var msgParams=new Array();
           msgParams[0]='<?php echo $paramScrollDelay;?>';
           msgParams[1]='<?php echo $paramRefreshDelay;?>';
           showInfo(i18n("enableRefreshDone",msgParams));
           formChanged();
           // Check if old animation is not still running
           var cancelAnimationFrame = window.cancelAnimationFrame || window.mozCancelAnimationFrame;
            if(typeof myReq !== 'undefined') {
             window.cancelAnimationFrame(myReq);
            }
            function animateScrollReport() {
              function scrollToAnchor(myNode) {
               if(typeof myNode !== 'undefined') {
                 dojox.fx.smoothScroll({
                    node: myNode,
                    win: dojo.byId('todayClassicView')
                 }).play();
               }
             }
             window.requestAnimationFrame = window.requestAnimationFrame || window.mozRequestAnimationFrame || window.webkitRequestAnimationFrame || window.msRequestAnimationFrame;
             var start = null;
             var reportNodes = dojo.query('#todayClassicView .dijitTitlePane');
             var nbReports = reportNodes.length;
              var nbTimes = 1;
             var i = 0;
              function step(timestamp) {
                var progress;
                if(nbReports == 0) { // When refreshing
                  reportNodes = dojo.query('#todayClassicView .dijitTitlePane');
                  nbReports = reportNodes.length;
                  requestAnimationFrame(step);
               } else {
                 if (start === null) start = timestamp;
                 progress = timestamp - start;
                 var scrollDelay=<?php echo $paramScrollDelay;?>;
                 if (progress > (scrollDelay * 1000 * nbTimes)) {
                   if(i >= reportNodes.length) {
                     i = 0;
                     ++nbTimes;
                    }
                   scrollToAnchor(reportNodes[i]);
                   if(i < reportNodes.length) {
                      ++i;
                      ++nbTimes;
                   }
                    myReq = requestAnimationFrame(step);
                 } else {
                    myReq = requestAnimationFrame(step);
                  }
                 }
             }
              requestAnimationFrame(step);
           }
            animateScrollReport();
           var refreshDelay=<?php echo $paramRefreshDelay;?>;
            refreshEnabled = setInterval(function() {
              formChangeInProgress=false;
              var cancelAnimationFrame = window.cancelAnimationFrame || window.mozCancelAnimationFrame;
              if(typeof myReq !== 'undefined') {
                window.cancelAnimationFrame(myReq);
              }
              loadMenuBarItem('Today', 'Today', 'tree');
              animateScrollReport();
            }, refreshDelay * 60 * 1000);
          } else {
            if(dojo.byId('isMenuLeftOpen').value=='false')dojo.byId( 'hideStreamNewGuiTopBar' ).click();
            exitFullScreen();
            formChangeInProgress=false;
            if (dojo.byId('statusBarDiv')) dojo.byId('statusBarDiv').style.top='30px';
            if (dijit.byId("toolBarDiv")) dijit.byId("toolBarDiv").resize({h :30});
            if (dijit.byId("statusBarDiv")) dijit.byId("statusBarDiv").resize({h :52});
            if (dojo.byId('menuBarShow')) dojo.byId('menuBarShow').style.top='81px';
            if (dojo.byId('centerDiv')) {
              dojo.byId('centerDiv').style.top='81px';
              var heightCenterDiv = dojo.byId('centerDiv').style.height;
              heightCenterDiv = heightCenterDiv.substring(0,heightCenterDiv.length-2);
              heightCenterDiv =  parseInt(heightCenterDiv)-81;
              dojo.byId('centerDiv').style.height=heightCenterDiv+'px';
            }
            showInfo(i18n("disableRefreshDone"));
            clearTimeout(refreshEnabled);
            var cancelAnimationFrame = window.cancelAnimationFrame || window.mozCancelAnimationFrame;
            if(typeof myReq !== 'undefined') {
              window.cancelAnimationFrame(myReq);
            }
            delete refreshEnabled;
          }
          </script>
        </button>
        <button id="todayParametersButton" dojoType="dijit.form.Button"
          showlabel="false" title="<?php echo i18n('menuParameter');?>"
          style="width: 28px" class="detailButton"
          iconClass="imageColorNewGui iconParameter iconSize22">
          <script type="dojo/connect" event="onClick" args="evt">
            loadDialog('dialogTodayParameters', null, true);
          </script>
        </button>
        <button id="todayPrintButton" dojoType="dijit.form.Button"
          showlabel="false" title="<?php echo i18n('print');?>"  class="detailButton"
          iconClass="dijitButtonIcon dijitButtonIconPrint">
          <script type="dojo/connect" event="onClick" args="evt">
            showPrint('../view/today.php');
          </script>
        </button>
        <?php 
        if($isModuleActive){
        $iconClass=($showActStream=='true')?'iconActivityStream22 iconActivityStream iconSize22':'iconActivityStreamClose22 iconActivityStreamClose iconSize22';?>
        <div id="todayAsticityStreamButton" dojoType="dijit.layout.ContentPane">
          <button id="todayShowActivityStream" dojoType="dijit.form.Button"
            showlabel="false" title="<?php echo ($showActStream=='true')?i18n('showActivityStream'):i18n('hideActivityStream');?>"  class="detailButton"
            iconClass=" <?php echo $iconClass;?> imageColorNewGui"  >
            <script type="dojo/connect" event="onClick" args="evt">
            showHideActivityStreamToday(<?php echo '\''.$showActStream.'\'';?>);
          </script>
          </button>   
        </div>
        <input id="defaultTodayActStreamWidth" value=<?php echo $widthForDisplay; ?>  type="hidden"/>
        <input id="todayActStreamIsActive" name="todayActStreamIsActive" value=<?php echo $showActStream; ?>  type="hidden"/>
        <?php }?>
      </div>

    <?php 
    } 
    
    
    $drawDiv=false;
    $coutTlist=count($todayList);
    $cp=0;
    foreach ($todayList as $todayItem) {
      $cp++;
      if ($todayItem->scope=='static' and $todayItem->staticSection=='Projects' ) {
          if (!$print) { 
          $titlePane="Today_project";?>
            <div dojoType="dijit.TitlePane"
              open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
              id="<?php echo $titlePane;?>"
              title="<?php echo i18n('menuProject');?>">
          <?php 
          } else {?>
             <div class="section"><?php echo i18n('menuProject');?></div> 
            <div>    
          <?php
          }
          showProjectsOld();
          ?>
           </div> 
          <?php
          if(!$print and $isModuleActive){
            echo '</div>';
          }
          else echo '<br/>';
      }else{
        if(!$drawDiv and !$print and $isModuleActive and $asTodayProject->id!=''){
          echo '<div dojoType="dijit.layout.ContentPane" region="left" style="width:'.$classicViewWidth.'; padding:15px;" splitter="true" id="todayClassicView" >';
            echo '<script type="dojo/connect" event="resize" args="evt">';
            echo 'saveContentPaneResizing("contentPaneTodayClassicViewWidth", dojo.byId("todayClassicView").offsetWidth, true);';
            echo 'saveContentPaneResizing("contentPaneTodayClassicViewHeight", dojo.byId("todayClassicView").offsetHeight, true);';
            echo '</script>';
          
          $drawDiv=true;
          
          // MSG   
          if (!$print or !pq_array_key_exists($titlePane, $collapsedList)) {
            showMessagesOld(true);
          }
          // Start Guide   
          $paramFirstPage=Parameter::getUserParameter('startPage');
          if ($paramFirstPage=='startGuide.php' and !$print) {
            $titlePane="Today_startGuide";
            ?>
                <div dojoType="dijit.TitlePane"
                    open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
                    id="<?php echo $titlePane;?>"
                    onHide="saveCollapsed('<?php echo $titlePane;?>');"
                    onShow="saveExpanded('<?php echo $titlePane;?>');"
                    title="<?php echo i18n('startGuideTitle');?>">  
                  <?php include "startGuide.php";?>
                </div>
                <br />
              <?php
              }
        }
        if ($todayItem->scope=='static' and $todayItem->staticSection=='AssignedTasks') {
          showAssignedTasksOld();
        } else if ($todayItem->scope=='static' and $todayItem->staticSection=='ResponsibleTasks') {
          showResponsibleTasksOld();
        }else if($todayItem->scope=='static' and $todayItem->staticSection=='ResponsibleTodoList' and Module::isModuleActive('moduleTodoList')){
          $showSubTask=false;
          foreach ($user->getAllProfiles() as $prof) {
            $showSubTaskObj=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$prof,'scope'=>'subtask'));
            if ($showSubTaskObj and $showSubTaskObj->id and $showSubTaskObj->rightAccess=='1') {
              $showSubTask=true;
            }
          }
        	if ($showSubTask) showSubTaskOld();
        } else if ($todayItem->scope=='static' and $todayItem->staticSection=='AccountableTasks') {
          showAccountableTasksOld();
        } else if ($todayItem->scope=='static' and $todayItem->staticSection=='IssuerRequestorTasks') {
          showIssuerRequestorTasksOld();
        } else if ($todayItem->scope=='static' and $todayItem->staticSection=='Documents') {
          //showDocumentsOld();
          showApproversOld();
        } else if ($todayItem->scope=='static' and $todayItem->staticSection=='ProjectsTasks') {
          if ($profile->profileCode=='PL') {
            showProjectsTasksOld();
          }
        } else if ($todayItem->scope=='report') {
          $rpt=new Report($todayItem->idReport);
          $titlePane="Today_report_".$todayItem->id;
          if (!$print or !pq_array_key_exists($titlePane, $collapsedList)) {
            if (!$print) {
              // echo '<div id="'.$titlePane.'_wait">... loading...</div>';
              echo '<div dojoType="dijit.TitlePane" style="overflow-x:auto"';
              echo ' open="'.(pq_array_key_exists($titlePane, $collapsedList)?'false':'true').'"';
              echo ' id="'.$titlePane.'"';
              echo ' title="'.i18n('colReport').' &quot;'.i18n($rpt->name).'&quot;" >';
              echo ' <script type="dojo/connect" event="onHide" args="evt">';
              echo ' saveCollapsed("'.$titlePane.'");';
              echo ' setTimeout(\'dijit.byId("'.$titlePane.'").set("content","");\',100);';
              echo ' </script>';
              echo ' <script type="dojo/connect" event="onShow" args="evt">';
              echo '   saveExpanded("'.$titlePane.'");';
              $params=TodayParameter::returnReportParameters($rpt);
              $paramsToday=TodayParameter::returnTodayReportParameters($todayItem);
              foreach ($paramsToday as $pName=>$pValue) {
                $params[$pName]=$pValue;
              }
              $urlParam=((pq_strpos($rpt->file, '?')>0)?'&':'?')."fromToday=true";
              foreach ($params as $paramName=>$paramValue) {
                $urlParam.=($urlParam or pq_strpos($rpt->file, '?')>0)?'&':'?';
                $urlParam.=$paramName.'='.$paramValue;
              }
              echo '   loadReport("../report/'.$rpt->file.$urlParam.'","'.$titlePane.'");';
              echo ' </script>';
              echo '<img src="../view/css/images/treeExpand_loading.gif" />';
            } else {
              echo '<div class="section">'.i18n('colReport').' &quot;'.i18n($rpt->name).'&quot;</div><br/><div>';
              $params=TodayParameter::returnReportParameters($rpt);
              $paramsToday=TodayParameter::returnTodayReportParameters($todayItem);
              foreach ($paramsToday as $pName=>$pValue) {
                $params[$pName]=$pValue;
              }
              $urlParam="";
              foreach ($params as $paramName=>$paramValue) {
                $_REQUEST[$paramName]=$paramValue;
              }
              $reportFile=pq_explode('?', $rpt->file);
              include '../report/'. $reportFile[0];
  	    }
  	  	echo '</div>';
  	  	echo '<br/>';
  	   }
  	
      }

    }
    if($cp==$coutTlist and $drawDiv ){
      echo '</div>';
    }

  } 
  if(!$print and $isModuleActive){
  if($asTodayProject->id==''){
      echo '</div>';
  }
  ?>
      
      <div dojoType="dijit.layout.ContentPane" id="todayActStream" region="center"  splitter="true" >
        <?php if($showActStream!='true')  include('../view/activityStreamList.php');?>
      <script type="dojo/connect" event="resize" args="evt">
          saveContentPaneResizing("contentPaneTodayActStreamWidth", dojo.byId("todayActStream").offsetWidth, true);
          <?php if($asTodayProject->id==''){?> saveContentPaneResizing("contentPaneTodayActStreamHeight", dojo.byId("todayActStream").offsetHeight, true);<?php }?>
          loadContent("activityStreamList.php", "todayActStream",null,null,null,null,null,null,true);  
          var show=(dojo.byId('todayActStreamIsActive'))?dojo.byId('todayActStreamIsActive').value:'false';
          if( show!='true' && dojo.byId("todayActStream").offsetWidth <=15  && !showHideActivityStreamTodayRun){
              resizeActivityStreamToday();
          }
      </script>
      </div>
    </div> 
<?php }?>
  </div>
</div>

<?php 

// all function for today

function showMessagesOld($addTitlePane=false) {
  global $cptMax,$collapsedList, $print;
  $titlePane="Today_message";
  $user=getSessionUser();
  $msg=new Message();
  if(sessionValueExists('showAllMessageTodayVal')){
    $showAllMessage=getSessionValue('showAllMessageTodayVal');
  }else if(RequestHandler::isCodeSet('showAllMessageToday')){
    $showAllMessage=RequestHandler::getValue('showAllMessageToday');
  }else{
    $showAllMessage='false';
  }
  $where="idle=0";
  $where.=" and (idUser is null or idUser='".Sql::fmtId($user->id)."')";
  $where.=" and (idProfile is null or idProfile in ".transformListIntoInClause($user->getAllProfiles()).")";
  $where.=" and (idProject is null or idProject in ".transformListIntoInClause($user->getVisibleProjects()).")";
  if ($user->idTeam) {
    $where.=" and (idTeam is null or idTeam = " . $user->idTeam . ")";
  } else {
    $where.=" and (idTeam is null)";
  }
  if ($user->idOrganization) {
    $orga=new Organization($user->idOrganization);
    $listOrga=$orga->getParentOrganizationStructure();
    $listOrga[$orga->id]=$orga->name;
    $where.=" and (idOrganization is null or idOrganization in " . transformListIntoInClause($listOrga). ")";
  } else {
    $where.=" and (idOrganization is null)";
  }
  $sort="id desc";
  $listMsg=$msg->getSqlElementsFromCriteria(null, false, $where, $sort);
  if (count($listMsg)>0 ) {
    if ($addTitlePane) {
      if (!$print) {?>
        <div dojoType="dijit.TitlePane"
          open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
          id="<?php echo $titlePane;?>"
          onHide="saveCollapsed('<?php echo $titlePane;?>');"
          onShow="saveExpanded('<?php echo $titlePane;?>');"
          title="<?php echo i18n('menuMessage');?>">  
     <?php } else { ?>
        <div class="section"><?php echo i18n('menuMessage');?></div>
        <br />
        <div>    
     <?php }
    }   
    $cpt=0;
    echo '<input id="showAllMessageToday" name="showAllMessageToday"  hidden value="'.$showAllMessage.'" />';
    echo '<form id="todayMessageForm" name="todayMessageForm">';
    echo '<table align="center" style="width:100%">';
    foreach ($listMsg as $msg) {
      #Florent ticket 4030
      $startDate=$msg->startDate;
      $endDate=$msg->endDate;
      $today=date('Y-m-d H:i:s');
      if( $startDate <= $today && $endDate >= $today or $startDate=='' && $endDate=='' or $startDate<= $today && $endDate==''){
          $cpt++;
          if ($cpt>$cptMax and $showAllMessage=='false') {
            echo '<tr><td colspan="2" class="messageData"><div>'.i18n('limitedDisplay', array($cptMax)).'</div><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconDisplayMore16" onclick="refreshTodayList(\'Message\',\'true\')" title="'.i18n('displayMore').'" >&nbsp;</div></td></tr>';
            break;
          }
          $type=new MessageType($msg->idMessageType);
          echo '<tr><td class="messageHeader" style="color:'.htmlEncode($type->color).';">'.htmlEncode($msg->name).'</td></tr>';
          echo '<tr><td class="messageData" >'.htmlEncode($msg->description, 'formatted').'</td></tr>';
          }
        else{
          
        } 
      }
    if($showAllMessage=='true'){
      echo '<tr style="text-align: center;font-weight:bold;"><td colspan="18"  class="messageData"><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconReduceDisplay16" onclick="refreshTodayList(\'Message\',\'false\')" title="'.i18n('reduceDisplayToday').'">&nbsp;</div></td></tr>';
    }
    echo '</table>';
    echo '</form>';
    if ($addTitlePane) {?>
      </div>
      <br /><?php
    }      
  }
}

function showProjectsOld() {
  global $cptMax, $print, $workVisibility, $templateProjectList, $arrayCols, $showCol, $cptCol;
  $user=getSessionUser();
  $parmSizeProject=Parameter::getUserParameter('sizeDisplayProjectToday');
  $prjVisLst=$user->getVisibleProjects();
  $prjLst=$user->getHierarchicalViewOfVisibleProjects(true);
  $lstProj=array();
  foreach ($prjLst as $idProject=>$p){
    $lstProj[]=pq_substr($idProject,1);
  }
  if(sessionValueExists('showAllProjectTodayVal')){
    $showAllProject=getSessionValue('showAllProjectTodayVal');
  }else if(RequestHandler::isCodeSet('showAllProjectToday')){
    $showAllProject=RequestHandler::getValue('showAllProjectToday');
  }else{
    $showAllProject='false';
  }
  $showProject=securityCheckDisplayMenu(null, 'Project');
  $showOne=false;
  if ($showProject) $showOne=true;
  foreach ($arrayCols as $col) {
    $cptFld='cpt'.$col;
    $$cptFld=$cptCol[$col];
    if ($showCol[$col]) $showOne=true;
  }
  $obj=new Project();
  $cptsubProject=$obj->countGroupedSqlElementsFromCriteria(null, array('idProject'), 'idProject in '.transformListIntoInClause($prjVisLst));
  $showIdle=false;
  $showDone=false;
  $countScope='todo';
  if (sessionValueExists('todayCountScope')) {
    $countScope=getSessionValue('todayCountScope');
  }
  if ($showOne and count($prjLst)>0) {
    echo '<div style="width:100%; overflow-x:auto" >';
    echo '<input id="showAllProjectToday" name="showAllProjectToday"  hidden value="'.$showAllProject.'" />';
    echo '<form id="todayProjectsForm" name="todayProjectsForm">';
    echo '<table align="center" style="width:100%">';
    echo '<tr><td style="text-align:left;width:10%" class="tabLabel" >';
    echo '<span class="nobr">'.i18n('titleCountScope').' : </span>';
    echo '</td>';
    if ($print) {
      echo '<td style="text-align:left;" class="tabLabel">';
      echo '<label>'.i18n('titleCount'.pq_ucfirst($countScope)).'&nbsp;</label>';
      echo '</td>';
    } else {
      
      echo '<td style="text-align:right; width:5%" class="tabLabel">';
      echo '<label for="countScopeTodo">'.i18n('titleCountTodo').'&nbsp;</label>';
      echo '</td><td style="text-align:left;" class="tabLabel">';
      echo '<input '
          .(($countScope=='todo')?'':'onChange="refreshTodayProjectsList();"')
          .' type="radio" dojoType="dijit.form.RadioButton" name="countScope" id="countScopeTodo" '
          .(($countScope=='todo')?'checked':'').' value="todo" />';
      echo '</td>';
      echo '<td style="text-align:right; width:5%" class="tabLabel">';
      echo '<label for="countScopeNotClosed">'.i18n('titleCountNotClosed').'&nbsp;</label>';
      echo '</td><td style="text-align:left;" class="tabLabel">';
      echo '<input '
          .(($countScope=='notClosed')?'':'onChange="refreshTodayProjectsList();"')
          .' type="radio" dojoType="dijit.form.RadioButton" name="countScope" id="countScopeNotClosed" '
          .(($countScope=='notClosed')?'checked':'').' value="notClosed" />';
      echo '</td>';
      echo '<td style="text-align:right; width:5%" class="tabLabel">';
      echo '<label for="countScopeAll">'.i18n('titleCountAll').'&nbsp;</label>';
      echo '</td><td style="text-align:left;" class="tabLabel">';
      echo '<input '
          .(($countScope=='all')?'':'onChange="refreshTodayProjectsList();"')
          .' type="radio" dojoType="dijit.form.RadioButton" name="countScope" id="countScopeAll" '
          .(($countScope=='all')?'checked':'').' value="all" />';
      echo '</td>';
      echo "<td style='width:50%'>&nbsp;</td>";
    }
    echo '</tr>';
    echo '</table></form>';
    $width=($print)?'45':'55';
    $lstProj=implode(",",$lstProj);
    echo '<table align="center" style="width:100%; ">';
    echo '<tr>'.'  <td class="messageHeader" colspan="'.(($showProject)?'1':'1').'" style="border-right:0">'.i18n('menuProject');
    if(!$print){
      echo '     <div id="showProjectToDay" class="ganttExpandOpened"';
      echo '      style="float:left; width:16px; height:13px;"';
      echo '      onclick="showProjectToDay(0,\''.$lstProj.'\')">&nbsp;&nbsp;&nbsp;&nbsp;</div>';
      echo '     <div id="hideProjectToDay" class="ganttExpandClosed"';
      echo '      style="float:left; width:16px; height:13px;"';
      echo '      onclick="showProjectToDay(1,\''.$lstProj.'\')">&nbsp;&nbsp;&nbsp;&nbsp;</div>';
    }
    echo '</td>';
    if ($showProject) {
      echo '<td class="messageHeader" style="border-left:0;border-right:0" title="'.i18n("Health").'"><div class="imageColorWhite iconHealth iconSize16"></div></td>';
      echo '<td class="messageHeader" style="border-left:0;border-right:0" title="'.i18n("Quality").'"><div class="imageColorWhite iconQuality iconSize16"></div></td>';
      echo '<td class="messageHeader" style="border-left:0;" title="'.i18n("Trend").'"><div class="imageColorWhite iconTrend iconSize16"></div></td>';
    }
    if ($showProject) echo '  <td class="messageHeader" colspan="2" width="'.($width).'px;"><div xstyle="width:50px; xoverflow: hidden; xtext-overflow: ellipsis;">'.pq_ucfirst(i18n('progress')).'</div></td>';
    if ($workVisibility=='ALL' and $showProject) {
      echo '  <td class="messageHeader" width="'.$width.'px;"><div xstyle="width:50px; xoverflow: hidden; xtext-overflow: ellipsis;">'.pq_ucfirst(i18n('colLeft')).'</div></td>';
      echo '  <td class="messageHeader" width="'.$width.'px;"><div xstyle="width:50px; xoverflow: hidden; xtext-overflow: ellipsis;">'.pq_ucfirst(i18n('colMargin')).'</div></td>';
    }
    if ($showProject) echo '  <td class="messageHeader" width="5%"><div xstyle="width:80px; xoverflow: hidden; xtext-overflow: ellipsis;">'.pq_ucfirst(i18n('colEndDate')).'</div></td>'
                          .'  <td class="messageHeader" width="5%"><div xstyle="width:60px; xoverflow: hidden; xtext-overflow: ellipsis;">'.pq_ucfirst(i18n('colLate')).'</div></td>';
    foreach ($arrayCols as $col) {
      if (!$showCol[$col]) continue;
      echo '  <td class="messageHeader" width="'.$width.'px;"><div style="width:'.($width+10).'px; overflow: hidden;text-align:center;text-overflow: hidden;">'.i18n('menu'.$col).'</div></td>';
    }
    echo '</tr>';
    $cpt=0;
    $countPro=-1;
    $levels=array();
    foreach ($prjLst as $sharpid=>$sharpName) {
      $cpt++;
      $visibleRows=array();
      $countPro++;
      if($parmSizeProject!='' and $parmSizeProject==$countPro and $showAllProject=='false'){
        echo '<tr style="text-align: center;font-weight:bold;"><td colspan="18"  class="messageData"><div >'.i18n('limitedDisplay', array($parmSizeProject)).'</div><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconDisplayMore16" onclick="refreshTodayProjectsList(\'true\')" title="'.i18n('displayMore').'" >&nbsp;</div></td></tr>';
        break;
      }
      $split=pq_explode('#', $sharpName);
      $wbs=$split[0];
      $name=pq_str_replace('&sharp;', '#', $split[1]);
      $id=pq_substr($sharpid, 1);
      $project= new Project($id);
      $isSubProj=$project->getTopProjectList();
      $listSub=array();
      $hiddenSubProj=true;
      //florent
      $subProj=$project->getSubProjectsList();
      $user=getCurrentUserId();
      $colParent = SqlElement::getSingleSqlElementFromCriteria('Collapsed', array('scope'=>'todayProjectRow_'.$id, 'idUser'=>$user));
      $idProj=$id;
      foreach ($subProj as $idSub=>$sub){
        $listSub[]=$idSub;
        $critArray=array('scope'=>'todayProjectRow_'.$idSub, 'idUser'=>$user);
        $col = SqlElement::getSingleSqlElementFromCriteria('Collapsed', $critArray);
          $visibleRows[]=$idSub;
        if($col->id=='' and $hiddenSubProj==true){
          $hiddenSubProj=false;
        }
        $newSub=new Project($idSub);
        $asSub=$newSub->getSubProjectsList();
        if($asSub){
          foreach ($asSub as $idsub2=>$sub2){
            $visibleRows[]=$idsub2;
          }
        }
      }
      $pose='';
      $showForced=false;
      if(count($isSubProj)!=0 ){
        $pose=pq_trim(pq_strpos($lstProj,$isSubProj[0]));
      }
      if($pose==''){
        $showForced=true;
      }
      if($colParent->id=="" and count($isSubProj)!=0 and  $showForced==false){
        continue;
      }
      if($hiddenSubProj ){
        $class="ganttExpandOpened";
      }else{
        $class="ganttExpandClosed";
      }
      //
      foreach ($arrayCols as $col) {
        $nbItem[$col]=countFromOld($cptCol[$col], $id, '', $countScope);
        $nbItemAll[$col]=countFromOld($cptCol[$col], $id, 'All', $countScope);
        $nbItemTodo[$col]=countFromOld($cptCol[$col], $id, 'Todo', $countScope);
        $nbItemDone[$col]=countFromOld($cptCol[$col], $id, 'Done', $countScope);
        $nbItem[$col]=($nbItemAll[$col]==0)?'':$nbItem[$col];
      }     
      $prjPE=SqlElement::getSingleSqlElementFromCriteria('ProjectPlanningElement', array('refType'=>'Project', 'refId'=>$id));
      $endDate=$prjPE->plannedEndDate;
      $endDate=($endDate=='')?$prjPE->validatedEndDate:$endDate;
      $endDate=($endDate=='')?$prjPE->initialEndDate:$endDate;
      $progress='0';
      if ($prjPE->realWork!='' and $prjPE->plannedWork!='' and $prjPE->plannedWork!='0') {
        $progress=$prjPE->progress;
      }
      $real=$prjPE->realWork;
      $left=$prjPE->leftWork;
      $margin=$prjPE->marginWorkPct;
      if ($margin!==null) {
        $margin='<div style="color:'.(($margin==0)?'#555555':(($margin<0)?'#DD0000':'#00AA00')).';">'.$margin.'&nbsp;%</div>';
      }
      $planned=$prjPE->plannedWork;
      $late='';
      if ($prjPE->plannedEndDate!='' and $prjPE->validatedEndDate!='') {
        $late=dayDiffDates($prjPE->validatedEndDate, $prjPE->plannedEndDate);
        $late='<div style="color:'.(($late>0)?'#DD0000':'#00AA00').';">'.$late;
        $late.=" ".i18n("shortDay");
        $late.='</div>';
      }
      $wbs=$prjPE->wbsSortable;
      $split=pq_explode('.', $wbs);
      //$level=count($split); // Old way...
      $level=0;
      $testWbs='';
      foreach($split as $sp) {
        $testWbs.=(($testWbs)?'.':'').$sp;
        if (isset($levels[$testWbs])) $level=$levels[$testWbs]+1;
      }
      $levels[$wbs]=$level;
      $tab="";
      for ($i=1; $i<=$level; $i++) {
        $tab.='&nbsp;&nbsp;&nbsp;';
        // $tab.='...';
      }
      $show=false;
      if (pq_array_key_exists($id, $prjVisLst)) {
        $show=true;
      }
      if (pq_array_key_exists($id, $templateProjectList)) {
        $show=false;
      }
      $cptSubPrj=(isset($cptsubProject[$id]))?$cptsubProject[$id]:0;
      if(count($prjLst)==1){
        $show=true;
      }
      if ($show or $cptSubPrj>0) {
        $goto="";
        $proj=new Project($id);
        if (!$print and $show and securityCheckDisplayMenu(null, 'Project') and pq_array_key_exists($id, $prjVisLst)) {
        // and securityGetAccessRightYesNo('menuProject', 'read', $prj)=="YES"
          $goto=' onClick="setSelectedProject(\''.htmlEnCode($proj->id).'\',\''.htmlEnCode($proj->name).'\',\'selectedProject\',\'null\',\'true\');" style="border-right:0px;text-align: left;cursor: pointer;'.($show?'':'color:#AAAAAA;').'" ';
        } else {
          $goto=' style="border-right:0px;text-align: left;"';
        }
        $styleHealth=($print)?'width:10px;height:10px;margin:1px;padding:0;-moz-border-radius:6px;border-radius:6px;border:1px solid #AAAAAA;':'';
        $healthColor=SqlList::getFieldFromId("Health", $proj->idHealth, "color");
        $healthIcon=SqlList::getFieldFromId("Health", $proj->idHealth, "icon");
        $healthName=i18n("colIdHealth").' : '.(($proj->idHealth)?SqlList::getNameFromId("Health", $proj->idHealth):i18n('undefinedValue'));
        $trendIcon=SqlList::getFieldFromId("Trend", $proj->idTrend, "icon");
        $trendColor=SqlList::getFieldFromId("Trend", $proj->idTrend, "color");
        $trendName=i18n("colIdTrend").' : '.(($proj->idTrend)?SqlList::getNameFromId("Trend", $proj->idTrend):i18n('undefinedValue'));
        $qualityColor=SqlList::getFieldFromId("Quality", $proj->idQuality, "color");
        $qualityIcon=SqlList::getFieldFromId("Quality", $proj->idQuality,"icon");
        $qualityName=i18n("colIdQuality").' : '.(($proj->idQuality)?SqlList::getNameFromId("Quality", $proj->idQuality):i18n('undefinedValue'));
        echo '<tr style="text-align: center;">';
        echo '  <td class="messageData" style="border-right:0">';
        if($subProj and !$print){
          echo '     <input id="group_asSub_'.$idProj.'" hidden value="'.implode(',', $listSub).'">';
          echo '     <div id="group_'.$idProj.'" class="'.$class.'"';
          echo '      style="float:left; width:16px; height:13px;"';
          echo '      onclick="expandProjectInToDay(\''.$idProj.'\',\''.implode(",", $listSub).'\',\''.implode(',', $visibleRows).'\');">&nbsp;&nbsp;&nbsp;&nbsp;</div>';
        }else{
          echo '     <div id="group_'.$idProj.'"';
          echo '      style="float:left; width:16px; height:13px;"';
          echo '     >&nbsp;&nbsp;&nbsp;&nbsp;</div>';
        }
        echo '<div '.$goto.' style="width:100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; " class="'.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'">'.$tab.htmlEncode($name);
        echo '</div></td>';
        if ($showProject) {
          $extraStyle="width:10px;margin:0;padding:0;spacing:0;border-left:0px;border-right:0px;margin:0 0px; padding:0 2px;width:16px; height:16px; width:16px;";
          $extraStyleImg="margin:0; padding:0;position:relative;top:2px; width:16px; height:16px;";
          $extraStyleColor="margin:0; padding:0;position:relative;top:1px; width:13px; height:13px;border-radius:8px;";
          if ($healthIcon) {
            echo ' <td class="messageData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="vertical-align:middle;'.$extraStyle.'" '.$goto.' >'.'<img height="16px" style="'.$extraStyleImg.'" src="icons/'.$healthIcon.'" title="'.$healthName.'"/>'.'  </td>';
          } else {
            echo '  <td class="messageData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="'.$extraStyle.'" '.$goto.' >'.'    <div class="colorHealth" style="'.$styleHealth.$extraStyleColor.'background:'.$healthColor.';" title="'.$healthName.'">&nbsp;</div>'.'  </td>';
          }
          if ($qualityIcon) {
            echo ' <td class="messageData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="vertical-align:middle;'.$extraStyle.'" '.$goto.' >'.(($qualityIcon)?'<img height="12px" style="'.$extraStyleImg.'" src="icons/'.$qualityIcon.'" title="'.$qualityName.'"/>':'').'  </td>';
          } else {
            echo '  <td class="messageData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="'.$extraStyle.'" '.$goto.' >'.'    <div class="colorHealth" style="'.$styleHealth.$extraStyleColor.'background:'.$qualityColor.';" title="'.$qualityName.'">&nbsp;</div>'.'  </td>';
          }
          if ($trendIcon) {
            echo ' <td class="messageData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="vertical-align:middle;'.$extraStyle.'" '.$goto.' >'.(($trendIcon)?'<img height="12px" style="'.$extraStyleImg.'" src="icons/'.$trendIcon.'" title="'.$trendName.'"/>':'').'  </td>';
          } else {
            echo '  <td class="messageData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="'.$extraStyle.'" '.$goto.' >'.'    <div class="colorHealth" style="'.$styleHealth.$extraStyleColor.'background:'.$trendColor.';" title="'.$healthName.'">&nbsp;</div>'.'  </td>';
          }
          
        }
        if ($showProject) echo '  <td style="width:'.$width.'px" class="messageDataValue'.($show?'':'Grey').' colorNameData">'.($show?displayProgressOld(htmlDisplayPct($progress), $planned, $left, $real, true, true):'').'</td>';
        if ($showProject) echo '  <td style="width:'.$width.'px" class="messageDataValue'.($show?'':'Grey').'">'.($show?SqlList::getNameFromId('OverallProgress', $proj->idOverallProgress):"").'</td>';
        if ($workVisibility=='ALL' and $showProject) {
          echo '  <td class="messageDataValue'.($show?'':'Grey').'">'.($show?Work::displayWorkWithUnit($left):'').'</td>';
          echo '  <td class="messageDataValue'.($show?'':'Grey').'">'.($show?$margin:'').'</td>';
        }
        if ($showProject) echo '  <td class="messageDataValue'.($show?'':'Grey').'" NOWRAP>'.($show?htmlFormatDate($endDate):'').'</td>'
                              .'  <td class="messageDataValue'.($show?'':'Grey').'">'.($show?$late:'').'</td>';
        foreach ($arrayCols as $col) {
          if (!$showCol[$col]) continue;
          echo '  <td class="messageDataValue'.($show?'':'Grey').' colorNameData" onclick=\'gotoElement("'.$col.'",null);stockHistory("'.$col.'",null,"object");setSelectedProject("'.htmlEnCode($proj->id).'","'.htmlEnCode($proj->name).'","selectedProject");\' style="cursor: pointer;">'.($show?displayProgressOld($nbItem[$col], $nbItemAll[$col], $nbItemTodo[$col], $nbItemDone[$col]):'').'</td>';
        }
        echo '</tr>';
      }
    }
    if($showAllProject=='true'){
      echo '<tr style="text-align: center;font-weight:bold;"><td colspan="18"  class="messageData"><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconReduceDisplay16" onclick="refreshTodayProjectsList(\'false\')" title="'.i18n('reduceDisplayToday').'">&nbsp;</div></td></tr>';
    }
    echo '</table>';
    echo '</div>';
  }
}

function showDocumentsOld() {
  if (!securityCheckDisplayMenu(null, 'Document')) return;
  $user=getSessionUser();
  $prjDocLst=$user->getVisibleProjects();
  $approver=new Approver();
  $critApprover=array('refType'=>"Document", 'idAffectable'=>$user->id);
  $critApprover2=array('refType'=>"DocumentVersion", 'approved'=>'1', 'idAffectable'=>$user->id);
  $critApprover3=array('refType'=>"Decision", 'approved'=>'0','idAffectable'=>$user->id);
  $listApprover=$approver->getSqlElementsFromCriteria($critApprover, false, null);
  $listApprover2=$approver->getSqlElementsFromCriteria($critApprover2, false, null);
  $listApprover3=$approver->getSqlElementsFromCriteria($critApprover3, false, null);
  $arrayDec=array();
  $arrayDoc=array();
  $arrayDocVers=array();
  // Liste of document version approved and approved by me
  foreach ($listApprover2 as $valApp2) {
    $docVers=new DocumentVersion($valApp2->refId);
    $doc=new Document($docVers->idDocument);
    if ($docVers->id==$doc->idDocumentVersion) {
      $arrayDocVers[$docVers->idDocument]=$doc->id;
    }
  }
  // List of document approved by me
  foreach ($listApprover as $valApp) {
    // recupérer version document new documentversion ($valApp->refId) , acceder au document , si iddocumentversion du document est bien la version recupérer dans le foreach , alors je stocke le $arrayDoc[iddudocument]
    $arrayDoc[$valApp->refId]=$valApp->refId;
  }
  foreach ($listApprover3 as $valApp) {
  	// recupérer version document new documentversion ($valApp->refId) , acceder au document , si iddocumentversion du document est bien la version recupérer dans le foreach , alors je stocke le $arrayDoc[iddudocument]
  	$arrayDec[$valApp->refId]=$valApp->refId;
  }
  $arrayD=array_diff($arrayDoc, $arrayDocVers);
  if (count($arrayD)==0) $arrayD=array(0=>" ");
  $whereDocument="id in ".transformListIntoInClause($arrayD);
  $whereActivity="1=0";
  $where=$whereActivity;
  $whereTicket=$where;
  $whereMeeting=$whereTicket;
  $whereDecision="id in ".transformListIntoInClause($arrayDec);
  $wherePokerSession = $where;
  showActivitiesListOld($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_DocumentDiv', 'documentsApproval');
}

function countFromOld($list, $idProj, $type, $scope) {
  $cpt00=(isset($list[$idProj.'|0|0']))?$list[$idProj.'|0|0']:0;
  $cpt01=(isset($list[$idProj.'|0|1']))?$list[$idProj.'|0|1']:0;
  $cpt10=(isset($list[$idProj.'|1|0']))?$list[$idProj.'|1|0']:0;
  $cpt11=(isset($list[$idProj.'|1|1']))?$list[$idProj.'|1|1']:0;
  if ($type=='All') {
    return $cpt00+$cpt01+$cpt10+$cpt11;
  } else if ($type=='Todo') {
    return $cpt00;
  } else if ($type=='Done') {
    return $cpt10;
  } else {
    if ($scope=='todo') {
      return $cpt00;
    } else if ($scope=='notClosed') {
      return $cpt00+$cpt10;
    } else {
      return $cpt00+$cpt01+$cpt10+$cpt11;
    }
  }
}

$cptDisplayId=0;

function displayProgressOld($value, $allValue, $todoValue, $doneValue, $showTitle=true, $isWork=false) {
  global $cptDisplayId, $print, $workVisibility;
  if (!$workVisibility) {
    $pe=new ProjectPlanningElement();
    $pe->setVisibility();
    $workVisibility=$pe->_workVisibility;
  }
  if ($value==='') {
    return $value;
  }
  $width=($print)?'45':'65';

  $green=($allValue!=0 and $allValue)?round($width*($allValue-$todoValue)/$allValue, 0):$width;
  $red=$width-$green;
  
  $cptDisplayId+=1;
  $result='<div style="position:relative; height:100%;width:'.$width.'px" id="displayProgress_'.$cptDisplayId.'">';
  $result.='<div style="overflow:hidden;position:absolute; height:100%;left:0px; width:'.$green.'px;background: #AAFFAA;">&nbsp;</div>';
  $result.='<div style="position:absolute; width:'.$red.'px;height:100%;left:'.$green.'px;background: #FFAAAA;">&nbsp;</div>';
  $result.='<div style="position:relative;">'.$value.'</div>';
  $result.='</div>';
  if ($showTitle and !$print and (!$isWork or $workVisibility=='ALL')) {
    $result.='<div dojoType="dijit.Tooltip" connectId="displayProgress_'.$cptDisplayId.'" position="below">';
    $result.="<table>";
    if ($isWork) {
      $result.='<tr style="text-align:right;"><td>'.i18n('real').'&nbsp;:&nbsp;</td><td style="background: #AAFFAA">'.Work::displayWorkWithUnit($doneValue).'</td></tr>';
      $result.='<tr style="text-align:right;"><td>'.i18n('left').'&nbsp;:&nbsp;</td><td style="background: #FFAAAA">'.Work::displayWorkWithUnit($todoValue).'</td></tr>';
      $result.='<tr style="text-align:right;font-weight:bold; border-top:1px solid #101010"><td>'.i18n('sum').'&nbsp;:&nbsp;</td><td>'.Work::displayWorkWithUnit($allValue).'</td></tr>';
    } else {
      $result.='<tr style="text-align:right;"><td>'.i18n('titleNbTodo').'&nbsp;:&nbsp;</td><td style="background: #FFAAAA">'.($todoValue).'</td></tr>';
      $result.='<tr style="text-align:right;"><td>'.i18n('titleNbDone').'&nbsp;:&nbsp;</td><td style="background: #AAFFAA">'.($doneValue).'</td></tr>';
      $result.='<tr style="text-align:right;"><td>'.i18n('titleNbClosed').'&nbsp;:&nbsp;</td><td style="background: #AAFFAA">'.($allValue-$todoValue-$doneValue).'</td></tr>';
      $result.='<tr style="text-align:right;font-weight:bold; border-top:1px solid #101010"><td>'.i18n('titleNbAll').'&nbsp;:&nbsp;</td><td>'.($allValue).'</td></tr>';
    }
    $result.='</table>';
    $result.='</div>';
  }
  return $result;
}

function showAssignedTasksOld() {
  if (!securityCheckDisplayMenu(null, 'Activity') and !securityCheckDisplayMenu(null, 'Meeting') ) return;
  $user=getSessionUser();
  $ass=new Assignment();
  $act=new Activity();
  $meet=new Meeting();
  $poker = new PokerSession();
  $where="1=0";
  $whereTicket=$where;
  $whereDocument=$where;
  $whereActivity=" (exists (select 'x' from ".$ass->getDatabaseTableName()." x "."where x.refType='Activity' and x.refId=".$act->getDatabaseTableName().".id and x.idResource=".Sql::fmtId($user->id).")".") and idle=0 and done=0";
  $whereMeeting=pq_str_replace(array('Activity', $act->getDatabaseTableName()), array('Meeting', $meet->getDatabaseTableName()), $whereActivity);
  $whereDecision=$where;
  $wherePokerSession = " (exists (select 'x' from ".$ass->getDatabaseTableName()." x "."where x.refType='PokerSession' and x.refId=".$poker->getDatabaseTableName().".id and x.idResource=".Sql::fmtId($user->id).")".") and idle=0 and done=0";
  showActivitiesListOld($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision,$wherePokerSession, 'Today_WorkDiv', 'todayAssignedTasks');
}

function showAccountableTasksOld() {
  if (!getSessionUser()->isResource) return;
  $user=getSessionUser();
  $where="1=0";
  $whereTicket="idAccountable='".Sql::fmtId($user->id)."' and idle=0 and done=0";
  $whereActivity=$where;
  $whereMeeting=$whereActivity;
  $whereDocument=$whereMeeting;
  $whereDecision=$where;
  $wherePokerSession=$where;
  showActivitiesListOld($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_AccDiv', 'todayAccountableTasks');
}

function showResponsibleTasksOld() {
  if (!getSessionUser()->isResource) return;
  $user=getSessionUser();
  $ass=new Assignment();
  $act=new Activity();
  $where="(idResource=".Sql::fmtId($user->id).") and idle=0 and done=0";
  $whereTicket=$where;
  $whereActivity=$where;
  $whereMeeting=$whereActivity;
  $whereDocument="1=0";
  $whereDecision=$whereDocument;
  $wherePokerSession=$where;
  showActivitiesListOld($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_RespDiv', 'todayResponsibleTasks');
}

function showIssuerRequestorTasksOld() {
  $user=getSessionUser();
  $where="(idUser='".Sql::fmtId($user->id)."'".") and idle=0 and done=0";
  $whereTicket="(idUser='".Sql::fmtId($user->id)."'"." or idContact='".Sql::fmtId($user->id)."'".") and idle=0 and done=0";
  $whereActivity=$whereTicket;
  $whereMeeting=$where;
  $whereDocument="1=0";
  $whereDecision=$whereDocument;
  $wherePokerSession=$where;
  showActivitiesListOld($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_FollowDiv', 'todayIssuerRequestorTasks');
}

function showProjectsTasksOld() {
  $where="(idProject in ".getVisibleProjectsList().") and idle=0 and done=0";
  $whereTicket=$where;
  $whereActivity=$where;
  $whereMeeting=$where;
  $whereDocument="1=0";
  $whereDecision=$whereDocument;
  $wherePokerSession=$where;
  showActivitiesListOld($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_ProjectTasks', 'todayProjectsTasks');
}

function showActivitiesListOld($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument, $whereDecision, $wherePokerSession, $divName, $title) {
  // Assign idRess idUser idCont Items
  // $where : NO YES YES NO Milestone, Risk, Action, Issue, Opportunity, Decision, Question, Quote, Order, Bill
  // $whereActivity : YES YES YES YES Activity
  // $whereTicket : NO YES YES YES Ticket
  // $whereMeeting : YES YES YES NO Meeting, TestSession
  global $cptMax, $print, $cptDisplayId, $collapsedList, $templateProjectList;
  $user=getSessionUser();
  $crit=array('idUser'=>$user->id, 'idToday'=>null, 'parameterName'=>'periodDays');
  $tp=SqlElement::getSingleSqlElementFromCriteria('TodayParameter', $crit);
  $periodDays=$tp->parameterValue;
  $crit=array('idUser'=>$user->id, 'idToday'=>null, 'parameterName'=>'periodNotSet');
  $tp=SqlElement::getSingleSqlElementFromCriteria('TodayParameter', $crit);
  $periodNotSet=$tp->parameterValue;
  $ass=new Assignment();
  $act=new Activity();
  $order="";
  $list=array();
  $ticket=new Ticket();
  $showAllLib=pq_substr($divName,6);
  if(sessionValueExists('showAll'.$showAllLib.'TodayVal')){
    $showAllToday=getSessionValue('showAll'.$showAllLib.'TodayVal');
  }else if(RequestHandler::isCodeSet('showAll'.$showAllLib.'Today')){
    $showAllToday=RequestHandler::getValue('showAll'.$showAllLib.'Today');
  }else{
    $showAllToday='false';
  }
  $listTicket=$ticket->getSqlElementsFromCriteria(null, null, $whereTicket, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listTicket);
  $activity=new Activity();
  $listActivity=$activity->getSqlElementsFromCriteria(null, null, $whereActivity, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listActivity);
  $milestone=new Milestone();
  $listMilestone=$milestone->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listMilestone);
  $risk=new Risk();
  $listRisk=$risk->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listRisk);
  $opportunity=new Opportunity();
  $listOpportunity=$opportunity->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listOpportunity);
  // gautier #2840
  $question=new Question();
  $listQuestion=$question->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listQuestion);
  // krowry #2915
  $document=new Document();
  $listDoc=$document->getSqlElementsFromCriteria(null, false, $whereDocument);
  $list=array_merge($list, $listDoc);
  $decision=new Decision();
  $listDec=$decision->getSqlElementsFromCriteria(null, false, $whereDecision);
  $list=array_merge($list, $listDec);
  $action=new Action();
  $listAction=$action->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listAction);
  $issue=new Issue();
  $listIssue=$issue->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listIssue);
  $meeting=new Meeting();
  $listMeeting=$meeting->getSqlElementsFromCriteria(null, null, $whereMeeting, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listMeeting);
  $poker=new PokerSession();
  $listPoker=$poker->getSqlElementsFromCriteria(null, null, $wherePokerSession, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listPoker);
  $session=new TestSession();
  $listSession=$session->getSqlElementsFromCriteria(null, null, pq_str_replace(array('Meeting', $meeting->getDatabaseTableName()), array(
      'TestSession', 
      $session->getDatabaseTableName()), $whereMeeting), $order, null, true, $cptMax+1);
  $list=array_merge($list, $listSession);
  $decision=new Decision();
  $listDecision=$decision->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listDecision);
  $requirement=new Requirement();
  $listRequirement=$requirement->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listRequirement);
  $quotation=new Quotation();
  $listQuotation=$quotation->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listQuotation);
  $command=new Command();
  $listCommand=$command->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listCommand);
  $bill=new Bill();
  $listBill=$bill->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listBill);
  $calltender=new CallForTender();
  $listcalltender=$calltender->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listcalltender);
  $tender=new Tender();
  $listtender=$tender->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listtender);
  $orderToProvider=new ProviderOrder();
  $listOrderToProvider=$orderToProvider->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listOrderToProvider);
  $providerTerm=new ProviderTerm();
  $listProviderTerm=$providerTerm->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listProviderTerm);
  $providerBill=new ProviderBill();
  $listProviderBill=$providerBill->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listProviderBill);
  $term=new Term();
  $listTerm=$term->getSqlElementsFromCriteria(null, null, $where, $order, null, true, $cptMax+1);
  $list=array_merge($list, $listTerm);
  
  if (!$print or !pq_array_key_exists($divName, $collapsedList)) {
    if (!$print and !(pq_array_key_exists('refresh'.$showAllLib, $_REQUEST))) {
      echo '<div id="'.$divName.'" dojoType="dijit.TitlePane"';
      echo ' open="'.(pq_array_key_exists($divName, $collapsedList)?'false':'true').'"';
      echo ' onHide="saveCollapsed(\''.$divName.'\');"';
      echo ' onShow="saveExpanded(\''.$divName.'\');"';
      echo ' title="'.pq_ucfirst(i18n($title)).'"';
      echo '>';
    } else {
      echo '<div class="section">'.pq_ucfirst(i18n($title)).'</div><br/><div>';
    }
    echo '<input id="showAll'.$showAllLib.'Today" name="showAll'.$showAllLib.'Today"  hidden value="'.$showAllToday.'" />';
    echo '<form id="today'.$showAllLib.'Form" name="today'.$showAllLib.'Form">';
    echo '<table align="center" style="width:100%">';
    echo '<tr>'.' <td class="messageHeader" width="6%">'.pq_ucfirst(i18n('colId')).'</td>'.' <td class="messageHeader" width="12%">'.pq_ucfirst(i18n('colIdProject')).'</td>'.'  <td class="messageHeader" width="12%">'.pq_ucfirst(i18n('colType')).'</td>'.'  <td class="messageHeader" width="40%">'.pq_ucfirst(i18n('colName')).'</td>'.'  <td class="messageHeader" width="8%">'.pq_ucfirst(i18n('colDueDate')).'</td>'.'  <td class="messageHeader" width="12%">'.pq_ucfirst(i18n('colIdStatus')).'</td>'.'  <td class="messageHeader" width="3%" title="'.i18n('isIssuerOf').'">'.pq_ucfirst(i18n('colIssuerShort')).'</td>'.'  <td class="messageHeader" width="3%" title="'.i18n('isAccountableOf').'">'.pq_ucfirst(i18n('colAccountableShort')).'</td>'.'  <td class="messageHeader" width="3%" title="'.i18n('isResponsibleOf').'">'.pq_ucfirst(i18n('colResponsibleShort')).'</td>'.'</tr>';
    $cpt=0;
    $listEcheance=array();
    foreach ($list as $elt) {
      $echeance="";
      if (property_exists($elt, 'idProject') and pq_array_key_exists($elt->idProject, $templateProjectList)) continue;
      $class=get_class($elt);
      if ($class=='Ticket') {
        $echeance=($elt->actualDueDateTime)?$elt->actualDueDateTime:$elt->initialDueDateTime;
        $echeance=pq_substr($echeance, 0, 10);
      } else if ($class=='Activity' or $class=='Milestone' or $class=="TestSession" or $class=="Meeting") {
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$class, 'refId'=>$elt->id));
        $echeance=($pe->realEndDate)?$pe->realEndDate:(($pe->plannedEndDate)?$pe->plannedEndDate:(($pe->validatedEndDate)?$pe->validatedEndDate:$pe->initialEndDate));
      } else if ($class=="Risk" or $class=="Issue" or $class=="Opportunity") {
        $echeance=($elt->actualEndDate)?$elt->actualEndDate:$elt->initialEndDate;
      } else if ($class=="Action") {
        $echeance=($elt->actualDueDate)?$elt->actualDueDate:$elt->initialDueDate;
      } else if ($class=='CallForTender') {
      	$echeance=$elt->expectedTenderDateTime;
      } else if ($class=='Tender') {
      	$echeance=($elt->offerValidityEndDate)?$elt->offerValidityEndDate:$elt->expectedTenderDateTime;
      } else if ($class=='ProviderOrder') {
      	$echeance=$elt->deliveryExpectedDate;      	
      } else if ($class=='ProviderTerm' or $class=='Bill') {
      	$echeance=$elt->date;      	
      } else if ($class=='ProviderBill') {
      	$echeance=($elt->paymentDueDate)?$elt->paymentDueDate:$elt->date;      	
      } else if ($class=='Quotation') {
       $echeance=$elt->validityEndDate;
      } else if ($class=='Command') {
      	$echeance=($elt->validatedEndDate)?$elt->validatedEndDate:$elt->initialEndDate;      	
      } else if ($class=='Term') {
      	$echeance=($elt->date)?$elt->date:(($elt->validatedDate)?$elt->validatedDate:$elt->plannedDate);      	
      }else if($class=='PokerSession'){
        $echeance=$elt->pokerSessionDate;
      }
      
      $listEcheance[$echeance.'#'.$class.'#'.$elt->id]=$elt;
    }
    ksort($listEcheance);
    foreach ($listEcheance as $idList=>$elt) {
      $cptDisplayId++;
      $idType='id'.get_class($elt).'Type';
      $class=get_class($elt);
      $split=pq_explode('#', $idList);
      $echeance=$split[0];
      if ($periodDays and $class != 'Document') {
        if (!$echeance) {
          if (!$periodNotSet) {
            continue;
          }
        } else {
          if ($echeance>addDaysToDate(date("Y-m-d"), $periodDays)) {
            continue;
          }
        }
      }
      $cpt++;
      if ($cpt>$cptMax and $showAllToday=='false') {
        echo '<tr><td colspan="9" class="messageData" style="text-align:center;"><div><b>'.i18n('limitedDisplay', array($cptMax)).'</b></div><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconDisplayMore16" onclick="refreshTodayList(\''.$showAllLib.'\',\'true\')" title="'.i18n('displayMore').'" >&nbsp;</div></td></tr>';
        break;
      }
      $status="";
      $statusColor="";
      $displayColorStatus="";
      if (property_exists($elt, 'idStatus')){
        $statusColor=SqlList::getFieldFromId('Status', $elt->idStatus, 'color');
        $status=SqlList::getNameFromId('Status', $elt->idStatus);
        $displayColorStatus = htmlDisplayColoredFull($status, $statusColor);
      }
      $status=($status=='0')?'':$status;
      $goto="";
      $classGoto=$class;
      if ($classGoto=='Ticket' and (!securityCheckDisplayMenu(null, $classGoto) or !securityGetAccessRightYesNo('menu'.$classGoto, 'read', $elt)=="YES")) {
        $classGoto='TicketSimple';
      }
      if($classGoto=='PokerSession'){
        $classGoto='PokerSessionVoting';
      }
      if (!$print and securityCheckDisplayMenu(null, $classGoto) and securityGetAccessRightYesNo('menu'.$classGoto, 'read', $elt)=="YES") {
        $goto=' onClick="gotoElement('."'".$classGoto."','".htmlEncode($elt->id)."'".');" style="cursor: pointer;" ';
      }
      $alertLevelArray=$elt->getAlertLevel(true,true);
      $alertLevel=$alertLevelArray['level'];
      $color="background-color:#FFFFFF";
      if ($alertLevel=='ALERT') {
        $color='background-color:#FFAAAA;';
      } else if ($alertLevel=='WARNING') {
        $color='background-color:#FFDDAA;';
      } else if ($alertLevel=='CRITICAL') {
        $color='background-color:#FF5555;';
      }
      echo '<tr '.$goto.' id="displayWork_'.$cptDisplayId.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" >';
      if (!$print and $alertLevel!='NONE') {
        echo '<div dojoType="dijit.Tooltip" connectId="displayWork_'.$cptDisplayId.'" position="below">';
        echo $alertLevelArray['description'];
        echo '</div>';
      }
      $type="";
      if(property_exists($elt, 'id'.$class.'Type')){
        $type = SqlList::getNameFromId($class.'Type', $elt->$idType);
      }
      echo '  <td class="messageData" style="'.$color.'">'.'<table><tr><td>'.formatIcon($class, 16, i18n($class)).'</td><td>&nbsp;</td><td>#'.$elt->id.'</td></tr></table></td>'.'  <td class="messageData" style="'.$color.'">'.htmlEncode(SqlList::getNameFromId('Project', $elt->idProject)).'</td>'.'  <td class="messageData" style="'.$color.'">'.$type.'</td>'.'  <td class="messageData" style="'.$color.'">'.htmlEncode($elt->name).'</td>'.'  <td class="messageDataValue" style="'.$color.'" NOWRAP>'.htmlFormatDate($echeance).'</td>'.'  <td class="messageData colorNameData" style="'.$color.'">'.$displayColorStatus.'</td>'.'  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox($user->id==$elt->idUser).'</td>';
      if (property_exists($elt, 'idAccountable')) echo '  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox($user->id==$elt->idAccountable).'</td>';
      else echo '  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox(null).'</td>';
      if (property_exists($elt, 'idAuthor')) {
        echo '  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox($user->id==$elt->idAuthor).'</td>';
      } else {
        echo '  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox($user->id==$elt->idResource).'</td>';
      }
      echo '</tr>';
    }
    if($showAllToday=='true'){
      echo '<tr style="text-align: center;font-weight:bold;"><td colspan="9"  class="messageData"><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconReduceDisplay16" onclick="refreshTodayList(\''.$showAllLib.'\',\'false\')" title="'.i18n('reduceDisplayToday').'">&nbsp;</div></td></tr>';
    }
    echo "</table>";
    echo "</div><br/>";
    echo "</form>";
  }
}

function showSubTaskOld(){
global $cptMax,$collapsedList,$print;
  $result='';
  $titlePane="Today_TodoList";
  if (!getSessionUser()->isResource) return;
  $user=getSessionUser();
  $todoList= new SubTask();
  $where="(idResource=".Sql::fmtId($user->id).") and idle=0 and done=0";
  $lstTodoList=$todoList->getSqlElementsFromCriteria(null,null,$where,'idProject ASC, refType ASC, refId ASC, handled ASC, paused ASC');
  
  if(!$print){
    $result.= '<div dojoType="dijit.TitlePane" open="'.( pq_array_key_exists($titlePane, $collapsedList)?'false':'true').'" id="'.$titlePane.'" onHide="saveCollapsed(\''.$titlePane.'\')" onShow="saveExpanded(\''.$titlePane.'\');" ';
    $result.= '   title="'.i18n('SubTask').'">';
  }else { 
    $result.= '<div class="section">'.i18n('SubTask').'</div><br /><div> ';
  }
  
  //$result.= '<input id="showAll'.$showAllLib.'Today" name="showAll'.$showAllLib.'Today"  hidden value="'.$showAllToday.'" />';
  $result.= '<form id="todayTodoListForm" name="todayTodoListForm">';
  $result.= '<table align="center" style="width:100%">';
  $result.= '<tr>'
                .'<td class="messageHeader" width="12%">'.pq_ucfirst(i18n('colIdProject')).'</td>'
                .'<td class="messageHeader" width="18%">'.pq_ucfirst(i18n('sectionMailItem')).'</td>'
                .'<td class="messageHeader" width="48%">'.pq_ucfirst(i18n('SubTask')).'</td>'
                .'<td class="messageHeader" width="12%">'.pq_ucfirst(i18n('colIdStatus')).'</td>'
                .'<td class="messageHeader" width="19%">'.pq_ucfirst(i18n('Priority')).'</td>'
                
            .'</tr>';
  
  $cpProject=0;
  $cpAct=0;
  if(!empty($lstTodoList)){
    $oldProj='';
    $cpProject=1;
    $cpAct=1;
    foreach ($lstTodoList as $todo){
      $status=($todo->paused==1)?i18n('subTaskStatusOnHold'):(($todo->handled==0)?'':i18n('colHandled'));
      $backgroundColor=($todo->paused==1)?"background-color:#E0E0E0;":(($status=='')?"":"background-color:#FACA77;");
      $idProject=$todo->idProject;
      $refId=$todo->refId;
      $refType=$todo->refType;
      $objTodo=new $refType ($refId);
      if($objTodo->idle)continue;
      $priority=new Priority($todo->idPriority);
      $colorPrio=$priority->color;
      $backgroundPrio=(pq_trim($colorPrio)!='')?'background-color:'.$colorPrio.';color:'.getForeColor($colorPrio).';':'';
      $goto='';
      $class=get_class($todo);
      
      $result.= '<tr style="height:32px;">';
      if($oldProj!=$idProject){
        $result = pq_str_replace('rowspanProj', $cpProject, $result);
        $result = pq_str_replace('rowspanAct', $cpAct, $result);
        $cpProject=1;
        $cpAct=1;
        $oldRefId='';
        $oldRefType='';
        $oldProj=$idProject;
        $project= new Project($idProject);
        $gotoProj='';
        $styleProj='vertical-align:middle;';
        $projClass=get_class($project);
        $rightReadProj=securityGetAccessRightYesNo('menu'.$projClass,'read',$project);
        $classDivProj='';
        $styleDivProj='';
        if ( securityCheckDisplayMenu(null,$projClass) and $rightReadProj=="YES") {
          $gotoProj=' onClick="gotoElement(\''.$projClass.'\',\''.htmlEncode($project->id).'\');" ';
          $styleProj.='cursor: pointer;';
          $styleDivProj.='float:left;';
          $classDivProj='classLinkName';
        }
        $projectName= $project->name;
        
        $result.=   '<td class="messageDataValue" rowspan="rowspanProj"  style="'.$styleProj.'" '.$gotoProj.'>'
//                       .'<div style="'.$styleDivProj.'margin-left:3%;" class="'.$classDivProj.'">' .formatIcon($projClass, 16, i18n($projClass)).'</div>'
                      .'<div style="text-align:left;'.$styleDivProj.'" class="'.$classDivProj.'" >&nbsp;'.$projectName.'</div>'
                    .'</td>';
      }else{
        $cpProject++;
      }
      
      if($oldRefId!=$refId or $oldRefType!=$refType){
        $result = pq_str_replace('rowspanAct', $cpAct, $result);
        $cpAct=1;
        $gotoRefType='';
        $gotoObject=false;
        $styleRefType='vertical-align:middle;';
        $classDivObj='';
        $styleDivObj='';
        $obj= new $refType ($refId);
        
        if($oldRefType!=$refType)$oldRefType=$refType;
        if($oldRefId!=$refId)$oldRefId=$refId;
        
        $rightReadObj=securityGetAccessRightYesNo('menu'.$refType,'read',$obj);
        if ( securityCheckDisplayMenu(null,$refType) and $rightReadObj=="YES") {
          $gotoObject=true;
          $gotoRefType=' onClick="gotoElement(\''.$refType.'\',\''.htmlEncode($refId).'\');" ';
          $styleRefType.='cursor: pointer;';
          $styleDivObj='float:left;';
          $classDivObj='classLinkName';
        }
        

        $result.=   '<td class="messageDataValue"  rowspan="rowspanAct" style="'.$styleRefType.'" '.$gotoRefType.'>'
            .'<table><tr><td>'
            .'<div style="'.$styleDivObj.'margin-left:3%;" class="'.$classDivObj.'">' .formatIcon($refType, 16, i18n($refType)).'</div>'
  	        .'</td><td>'
            .'<div style="text-align:left;margin-left:5px;'.$styleDivObj.'" class="'.$classDivObj.'" >'.$obj->name.'</div>'
  	        .'</td></tr></table>'
            .'</td>';

      }else {
        $cpAct++;
      }
 
      $goto='';
      $style='';
      $classDiv='';
      if($gotoObject){
        $goto=$gotoRefType;
        $style='cursor: pointer;';
        $classDiv='classLinkName';
      }

      

      $result.=   '<td class="messageDataValue '.$classDiv.'" style="text-align:left;'.$style.'" '.$goto.'><div style="margin:5px;"><span>'.$todo->name.'</span></div></td>';
      $result.=   '<td class="messageDataValue" style="'.$backgroundColor.'"><div style=margin:5px;;">'.$status.'</div></td>';
      $result.=   '<td class="messageDataValue" style="'.$backgroundPrio.'"><div style="margin:5px;">'.$priority->name.'</div></td>';
      $result.= '</tr>';
    }
  }
  $result = pq_str_replace('rowspanProj', $cpProject, $result);
  $result = pq_str_replace('rowspanAct', $cpAct, $result);
  
  $result.= '</table>';
  $result.= '</form>';
  $result.= '</div>';
  
  echo $result;
}

function showApproversOld(){
  global $cptMax, $print, $cptDisplayId, $collapsedList;
  $result='';
  $showAllLib='Approvers';
  $divName = 'documentsApproval';
  $title = 'TodayApprovers';
  if(sessionValueExists('showAll'.$showAllLib.'TodayVal')){
    $showAllToday=getSessionValue('showAll'.$showAllLib.'TodayVal');
  }else if(RequestHandler::isCodeSet('showAll'.$showAllLib.'Today')){
    $showAllToday=RequestHandler::getValue('showAll'.$showAllLib.'Today');
  }else{
    $showAllToday='false';
  }
  if (!getSessionUser()->isResource) return;
  $user=getSessionUser();
  if (!$print or !pq_array_key_exists($divName, $collapsedList)) {
    if (!$print and !(pq_array_key_exists('refresh'.$showAllLib, $_REQUEST))) {
      echo '<div id="'.$divName.'" dojoType="dijit.TitlePane"';
      echo ' open="'.(pq_array_key_exists($divName, $collapsedList)?'false':'true').'"';
      echo ' onHide="saveCollapsed(\''.$divName.'\');"';
      echo ' onShow="saveExpanded(\''.$divName.'\');"';
      echo ' title="'.pq_ucfirst(i18n($title)).'"';
      echo '>';
    } else {
      echo '<div class="section">'.pq_ucfirst(i18n($title)).'</div><br/><div>';
    }
    echo '<input id="showAll'.$showAllLib.'Today" name="showAll'.$showAllLib.'Today"  hidden value="'.$showAllToday.'" />';
    echo '<form id="today'.$showAllLib.'Form" name="today'.$showAllLib.'Form">';
    echo '<table align="center" style="width:100%">';
    echo '<tr>'.' <td class="messageHeader" width="6%">'.pq_ucfirst(i18n('colId')).'</td>'.' <td class="messageHeader" width="12%">'.pq_ucfirst(i18n('colIdProject')).'</td>'.'  <td class="messageHeader" width="12%">'.pq_ucfirst(i18n('colType')).'</td>'.'  <td class="messageHeader" width="40%">'.pq_ucfirst(i18n('colName')).'</td>'.'  <td class="messageHeader" width="8%">'.pq_ucfirst(i18n('colDueDate')).'</td>'.'  <td class="messageHeader" width="12%">'.pq_ucfirst(i18n('colIdStatus')).'</td>'.'  <td class="messageHeader" width="3%" title="'.i18n('isIssuerOf').'">'.pq_ucfirst(i18n('colIssuerShort')).'</td>'.'  <td class="messageHeader" width="3%" title="'.i18n('isAccountableOf').'">'.pq_ucfirst(i18n('colAccountableShort')).'</td>'.'  <td class="messageHeader" width="3%" title="'.i18n('isResponsibleOf').'">'.pq_ucfirst(i18n('colResponsibleShort')).'</td>'.'</tr>';
    $cpt=0;
    $approver = new Approver();
    $lstApprover = $approver->getSqlElementsFromCriteria(array('approved'=>'0', 'idAffectable'=>$user->id, 'idle'=>'0'));
    
    foreach ($lstApprover as $app){
      if ($app->refType=='Document'){
        continue;
      }
      $extraName="";
      if($app->refType=='DocumentVersion'){
        //continue;
        $docVers=new DocumentVersion($app->refId);
        $doc=new Document($docVers->idDocument);
        if ($docVers->id!=$doc->idDocumentVersion) continue;
        if ($doc->idle or $doc->cancelled) continue;
        $app->refType='Document';
        $app->refId=$docVers->idDocument;
        $extraName=' - '.$docVers->name;
      }
      $elt = new $app->refType($app->refId);
      $class = get_class($elt);
      if ($elt->idle or (property_exists($class, 'cancelled') and $elt->cancelled)) continue;
      $cpt++;
      if ($cpt>$cptMax and $showAllToday=='false') {
        echo '<tr><td colspan="9" class="messageData" style="text-align:center;"><div><b>'.i18n('limitedDisplay', array($cptMax)).'</b></div><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconDisplayMore16" onclick="refreshTodayList(\''.$showAllLib.'\',\'true\')" title="'.i18n('displayMore').'" >&nbsp;</div></td></tr>';
        break;
      }
      $idType='id'.get_class($elt).'Type';
      $type="";
      $echeance="";
      $goto="";
      $classGoto=$class;
      if (!$print and securityCheckDisplayMenu(null, $classGoto) and securityGetAccessRightYesNo('menu'.$classGoto, 'read', $elt)=="YES") {
        $goto=' onClick="gotoElement('."'".$classGoto."','".htmlEncode($elt->id)."'".');" style="cursor: pointer;" ';
      }
      $status="";
      $statusColor="";
      $displayColorStatus="";
      if (property_exists($elt, 'idStatus')){
        $statusColor=SqlList::getFieldFromId('Status', $elt->idStatus, 'color');
        $status=SqlList::getNameFromId('Status', $elt->idStatus);
        $displayColorStatus = htmlDisplayColoredFull($status, $statusColor);
      }
      $status=($status=='0')?'':$status;
      $alertLevelArray=$elt->getAlertLevel(true,true);
      $alertLevel=$alertLevelArray['level'];
      $color="background-color:#FFFFFF";
      if ($alertLevel=='ALERT') {
        $color='background-color:#FFAAAA;';
      } else if ($alertLevel=='WARNING') {
        $color='background-color:#FFDDAA;';
      } else if ($alertLevel=='CRITICAL') {
        $color='background-color:#FF5555;';
      }
      echo '<tr '.$goto.' id="displayWork_'.$cptDisplayId.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" >';
      if (!$print and $alertLevel!='NONE') {
        echo '<div dojoType="dijit.Tooltip" connectId="displayWork_'.$cptDisplayId.'" position="below">';
        echo $alertLevelArray['description'];
        echo '</div>';
      }
      
      
      if(property_exists($elt, $idType)){
        $type = SqlList::getNameFromId($class.'Type', $elt->$idType);
      }
      $nameProject=(property_exists($elt, 'idProject'))?htmlEncode(SqlList::getNameFromId('Project', $elt->idProject)):'';
      echo '  <td class="messageData" style="'.$color.'">'.'<table><tr><td>'.formatIcon($class, 16, i18n($class)).'</td><td>&nbsp;</td><td>#'.$elt->id.'</td></tr></table></td>'.'  <td class="messageData" style="'.$color.'">'.$nameProject.'</td>'.'  <td class="messageData" style="'.$color.'">'.$type.'</td>'.'  <td class="messageData" style="'.$color.'">'.htmlEncode($elt->name.$extraName).'</td>'.'  <td class="messageDataValue" style="'.$color.'" NOWRAP>'.htmlFormatDate($echeance).'</td>'.'  <td class="messageData colorNameData" style="'.$color.'">'.$displayColorStatus.'</td>';
      if (property_exists($elt, 'idUser')){
        echo '<td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox($user->id==$elt->idUser).'</td>';
      }else{
        echo '<td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox(null).'</td>';
      }
      if (property_exists($elt, 'idAccountable')) echo '  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox($user->id==$elt->idAccountable).'</td>';
      else echo '  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox(null).'</td>';
      if (property_exists($elt, 'idAuthor')) {
        echo '  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox($user->id==$elt->idAuthor).'</td>';
      } else if(property_exists($elt, 'idResource')){
        echo '  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox($user->id==$elt->idResource).'</td>';
      } else if(property_exists($elt, 'idResponsible')){
        echo '  <td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox($user->id==$elt->idResponsible).'</td>';
      }else{
        echo '<td class="messageDataValue" style="'.$color.'">'.htmlDisplayCheckbox(null).'</td>';
      }
      echo '</tr>';
      if($showAllToday=='true'){
        echo '<tr style="text-align: center;font-weight:bold;"><td colspan="9"  class="messageData"><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconReduceDisplay16" onclick="refreshTodayList(\''.$showAllLib.'\',\'false\')" title="'.i18n('reduceDisplayToday').'">&nbsp;</div></td></tr>';
      }
    }
    echo "</table>";
    echo "</div><br/>";
    echo "</form>";
  }
  echo $result;
}
?>
