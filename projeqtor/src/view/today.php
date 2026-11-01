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
if (! isNewGui()) { // Set Old Today
  include '../view/today.old.php';
  exit;
}
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
  $refreshTab=RequestHandler::getValue('refreshProjectTab');
  $refreshShowProject=RequestHandler::getValue('showAllProjectToday');
  showProjects($refreshTab, $refreshShowProject);
  exit;
}
if(pq_array_key_exists('refreshMessage', $_REQUEST)) {
  showMessages();
  exit;
}

if(RequestHandler::isCodeSet('refreshTasks')) {
  $selection=RequestHandler::getValue('refreshTasks');
  Parameter::storeUserParameter('todayActivityListSelected', $selection);
  if ($selection=='Responsible') showResponsibleTasks();
  else if ($selection=='Assigned')   showAssignedTasks();
  else if ($selection=='IssuerRequestor') showIssuerRequestorTasks();
  else echo "invalid parameter for todayActivityListSelected='$selection'";
  exit;
}

if(pq_array_key_exists('refreshDocumentDiv', $_REQUEST)) {
  //showDocuments();
  showApprovers();
  exit;
}
if(pq_array_key_exists('refreshTodoList', $_REQUEST)) {
  showSubTask();
  exit;
}
if(pq_array_key_exists('refreshWorkDiv', $_REQUEST)) {
  showAssignedTasks();
  exit;
}
if(pq_array_key_exists('refreshRespDiv', $_REQUEST)) {
  showResponsibleTasks();
  exit;
}
if(pq_array_key_exists('refreshFollowDiv',$_REQUEST)) {
  showIssuerRequestorTasks();
  exit;
}

$today=new Today();
$crit=array('idUser'=>$user->id, 'idle'=>'0','scope'=>'newGui');
$todayList=$today->getSqlElementsFromCriteria($crit, false, null, 'sortOrder asc');
$asTodayProject=$today->getSingleSqlElementFromCriteria(get_class($today), array('scope'=>'newGui','staticSection'=>'Projects','idUser'=>$user->id, 'idle'=>'0'));
// initialize if empty
if (count($todayList)==0) {
  Today::insertStaticItems();
  $todayList=$today->getSqlElementsFromCriteria($crit, false, null, 'sortOrder asc');
  $asTodayProject=$today->getSingleSqlElementFromCriteria(get_class($today), array('scope'=>'newGui','staticSection'=>'Projects','idUser'=>$user->id, 'idle'=>'0'));
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
$menu =new Menu(177); // ActivityStream
if (!Module::isMenuActive($menu->name))  $isModuleActive=false;
if (!securityCheckDisplayMenu($menu->id,pq_substr($menu->name,4)))$isModuleActive=false;
$user=getSessionUser();

$tabShowTodaySection = array();
foreach ($todayList as $tdl){
  if($tdl->staticSection and $tdl->idle==0){
    $tabShowTodaySection[$tdl->staticSection]=$tdl->sortOrder;
  }
}
asort($tabShowTodaySection);
?>

<input type="hidden" name="objectClassManual" id="objectClassManual" value="Today" />
<div class="container" dojoType="dijit.layout.BorderContainer">
  <div class="backgroundToday" style="width:100%; height:100%;position:absolute;opacity:0.3 !important;z-index:-2">&nbsp;</div>
  <div class="backgroundToday" style="width:250%; height:250%;position:absolute;opacity:0.05 !important;top:-50%;z-index:-2">&nbsp;</div>
 <div style="overflow: <?php echo(!$print)?'auto':'hidden';?>;padding:2%;margin:2%'; ?>" id="detailDiv" dojoType="dijit.layout.ContentPane" region="center">
      <script type="dojo/connect" event="onShow" args="evt">
        <?php Parameter::setDisplaySM();?>
	    </script>
      <div class="simple-grid-top" style="width:100%;height:50px" >
      <div style="width:0px;height:0px;" class="today projeqtorReference">
        <button id="todayParametersButton" dojoType="dijit.form.Button"
          showlabel="false" title="<?php echo i18n('menuParameter');?>"
          style="position:absolute;right:45px;width: 28px;top:-10px;" class="detailButton"
          iconClass="imageColorNewGui iconParameter iconSize32">
          <script type="dojo/connect" event="onClick" args="evt">
            loadDialog('dialogNewTodayParameters', null, true);
          </script>
        </button>
      </div>
      <table >
        <tr><td style="font-size:50%"><?php echo i18n("welcomeMessage");?></td> <td style="font-size:50%"> <span style="margin-right: 10px;margin-left:10px;"></span></td>
        <td style="font-size:50%;font-weight:normal;color:#AAAAAA;text-align:right"><?php echo ($user->resourceName)?$user->resourceName:$user->name;?></td></tr>
      </table>
    </div>
    <div class="simple-grid " dojotype="dojo.dnd.Source" id="dndListToday" jsId="dndListToday" withhandles="false"  data-dojo-props="accept: ['today'],horizontal: true, singular:true">
    
    
    <?php foreach ($tabShowTodaySection as $nameSection=>$sortOrder){?>
      
      <?php
      if($nameSection=='Projects'){
      if(isset($tabShowTodaySection['Projects'])){?>
      <div id="Projects" dndType="today" class="dojoDndItem simple-grid__cell simple-grid__cell--1-2" style="min-width:900px">
        <div class="simple-grid__header"></div>
        <div id="showProjects" class="simple-grid__container" <?php if(count($tabShowTodaySection)==1){?> style="height:90%;" <?php }?>  ><?php showProjects();?></div>
      </div>
      <?php } }?>
      
      <?php 
         if($nameSection=='Message'){
         if(isset($tabShowTodaySection['Message'])){?>
      <div id="Message" dndType="today" class="dojoDndItem simple-grid__cell simple-grid__cell--1-4" style="">
        <div class="simple-grid__header"></div>
        <div id="showMessages" class="simple-grid__container" style=""><?php showMessages(true);?></div>
      </div> 
      <?php }} ?>
      
     <?php 
     if($nameSection=='Documents'){
     if(isset($tabShowTodaySection['Documents'])){?> 
      <div id="Documents" dndType="today" class="dojoDndItem simple-grid__cell simple-grid__cell--1-5" style="">
        <div class="simple-grid__header"></div>
        <div id="hideDocuments" class="simple-grid__container"><?php showApprovers();?></div>
      </div>
      <?php }} ?>
      
      <?php
      if($nameSection=='Todo'){
      if(isset($tabShowTodaySection['Todo'])){?> 
      <div  id="Todo" dndType="today" class="dojoDndItem simple-grid__cell simple-grid__cell--1-2" style=" min-width:900px; position:relative">
        <div class="simple-grid__header"></div>
        <div id="hideTodo">
          <div class="simple-grid__container" style="margin-left:75px;min-width:750px;min-height:282px;" id="todayTasksDiv" >
            <?php 
               //$arrayTasks=array("Responsible","Assigned","IssuerRequestor");
               $table=1;
               $table=Parameter::getUserParameter('todayActivityListSelected');
               if (!$table or $table=='') $table="Responsible";
               if ($table=="Responsible") showResponsibleTasks();
               else if ($table=="Assigned") showAssignedTasks();
               else if ($table=="IssuerRequestor") showIssuerRequestorTasks();
               else if ($table=="Projects") showProjectsTasks();
               else if ($table=="Accountable") showAccountableTasks();
               else echo "invalid parameter for todayActivityListSelected='$table'";
            ?>
          </div>
          <div class="" style="position:absolute; top:7px; width:50px;float:left;margin-left:15px;">
            <?php 
            $selectedResponsible=($table=='Responsible')?'Selected':'';
            $selectedAssigned=($table=='Assigned')?'Selected':'';
            $selectedIssuerRequestor=($table=='IssuerRequestor')?'Selected':'';
            ?>
            <div id="todayResponsibleTasksButton" class="todayIconTasks<?php echo $selectedResponsible?>" title="<?php echo i18n("todayResponsibleTasks");?>" onClick="todaySwithTasks('Responsible');" >
              <div id="todayResponsibleTasksButtonIcon" class="iconTopMenuUserParameter iconButton iconSize32 iconHumanResource" style="margin:auto;margin-top:10px"></div>
            </div>
            <div id="todayAssignedTasksButton" class="todayIconTasks<?php echo $selectedAssigned?>" title="<?php echo i18n("todayAssignedTasks");?>" onClick="todaySwithTasks('Assigned');">
              <div id="todayAssignedTasksButtonIcon" class="iconTopMenuUserParameter iconButton iconSize32 iconResource" style="margin:auto;margin-top:10px"></div>
            </div>
            <div id="todayIssuerRequestorTasksButton" class="todayIconTasks<?php echo $selectedIssuerRequestor?>" title="<?php echo i18n("todayIssuerRequestorTasks");?>" onClick="todaySwithTasks('IssuerRequestor');">
              <div id="todayIssuerRequestorTasksButtonIcon" class="iconTopMenuUserParameter iconButton iconSize32 iconContact" style="margin:auto;margin-top:10px;" ></div>
            </div>
          </div>
        </div>
      </div>
       <?php }} ?>
      
      
        <?php 
        if($nameSection=='News'){
        if(isset($tabShowTodaySection['News'])){ ?> 
      <div id="News"  dndType="today" class="dojoDndItem simple-grid__cell simple-grid__cell--1-4" style="">
         <div class="simple-grid__header"></div>
         <div id="hideNews" class="simple-grid__container" style="min-width:420px;max-height:400px;height:282px;">
               <div onMouseOver="dojo.byId('hideNewsDiv').style.display='block';" onMouseOut="dojo.byId('hideNewsDiv').style.display='none';">
           <table style="width:100%;">
             <tr>
               <td class="simple-grid__header"> <?php echo i18n('whatsnew');?></td>
               <td style="float:right;">
                <?php 
                echo '   <div  title="'.i18n('hideDivToday').'" id="hideNewsDiv" style="opacity:40%;display:none;width:24px;position:relative;float:right;">';
                $image='../view/css/images/tabClose.svg';
                echo '<img class="roundedButtonSmall  iconSize22" src="'.$image.'" onClick="hideDivToday(\'hideNews\');setTodayParameterHideSection(\'News\');" />';
                echo '</div>'; ?>
               </td>
             </tr>  
           </table>
                </div>
           <div class="transparentBackground" style="height:250px;margin-top:10px;">   
           <?php 
           $isTodayScreen = true;
           include('../view/activityStreamList.php');?>
           </div>
         </div>
      </div> 
      <?php }} ?> 
      
      
     <?php 
     if($nameSection=='ResponsibleTodoList'){
     if(Module::isModuleActive('moduleTodoList') and isset($tabShowTodaySection['ResponsibleTodoList'])){?>
      <div id="ResponsibleTodoList" dndType="today" class="dojoDndItem simple-grid__cell simple-grid__cell--1-5" style="">
        <div class="simple-grid__header"></div>
        <div id="hideTodoList" class="simple-grid__container" style="min-width:350px;max-height:400px;height:285px;"><?php showSubTask();?></div>
      </div> 
      <?php }
     }?>
     
     
     <?php $idReport = (isset(explode('_', $nameSection)[1]))?explode('_', $nameSection)[1]:null;
     $reportDivClass = (Parameter::getUserParameter('todayReportDivClass'.$idReport) != '')?Parameter::getUserParameter('todayReportDivClass'.$idReport):'simple-grid__cell--1-1';
     if($idReport){?>
      <div id="Report_<?php echo $idReport;?>" dndType="today" class="dojoDndItem simple-grid__cell <?php echo $reportDivClass;?>" style="position:relative">
        <div class="simple-grid__header"></div>
        <div class="simple-grid__container" style=""><?php showReport($idReport); ?></div>
      </div>
    <?php }?>
    
  <?php  } ?>
      </div>     
    </div>
  </div>
</div>

<?php 

// all function for today

function showActivityStreamNew(){
echo '<div>';
echo '  <table style="width:100%"><tr>';
echo '   <td class="simple-grid__header">'.i18n('activityStream').'</td>';
echo '  </tr>';
echo '  </table><table style="width:100%">';
echo '  <tr>&nbsp;</tr>';
echo '  <tr>';
echo '  <td></td>';
echo '  </tr>';
echo '  </table>';
echo '</div>';
}

function showMessages($addTitlePane=false) {
  global $cptMax,$collapsedList, $print;
  echo '<div  style="z-index:1000;" onMouseOver="dojo.byId(\'hideShowMessage\').style.display=\'block\';" onMouseOut="dojo.byId(\'hideShowMessage\').style.display=\'none\';" class="">';
  
  echo '  <table style="width:100%"><tr>';
  echo '   <td class="simple-grid__header">'.i18n('Message').'</td>';
  echo '<td>';
  echo '<div  title="'.i18n('hideDivToday').'" id="hideShowMessage" style="display:none;opacity:40%;width:24px;position:relative;top:2px;float:right;">';
  $image='../view/css/images/tabClose.svg';
  echo '<img class="roundedButtonSmall  iconSize22" src="'.$image.'" onClick="hideDivToday(\'showMessages\');setTodayParameterHideSection(\'Message\');" />';
  echo "</div>";
  
  echo '</td>';
  echo '  </tr>';
  echo '  </table>';
  echo '</div>';
  
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
  $today=date('Y-m-d H:i:s');
  $where.=" and (startDate is null or startDate<='$today') and (endDate is null or endDate>='$today')";
  $sort="id desc";
  $listMsg=$msg->getSqlElementsFromCriteria(null, false, $where, $sort);
  ?>
  <div style="height:250px !important; position: relative; overflow:hidden;" >
  <div data-dojo-type="dojox/mobile/PageIndicator" data-dojo-props='fixed:"top"'></div>
  <?php 
  if (count($listMsg)==0) {
    echo '<div class="todayData" style="width:100%;text-align:center;font-style:italic;color:#A0A0A0">'.i18n('noDataToDisplay').'</div>';
  }
  if (count($listMsg)>0 ) {
      $cpt=0;
      foreach ($listMsg as $msg) {
        $classMsg="statusBar";
        $startDate=$msg->startDate;
        $endDate=$msg->endDate;
        
        //if( $startDate <= $today && $endDate >= $today or $startDate=='' && $endDate=='' or $startDate<= $today && $endDate==''){
          $borderColor=SqlList::getFieldFromId('MessageType', $msg->idMessageType, 'color');
        ?>
        <div class="swapView " data-dojo-type="dojox/mobile/SwapView" id="divNews<?php echo $cpt;?>" name="divNews<?php echo $cpt;?>"> 
          <div style="height:225px !important; position: relative; overflow-x:hidden; overflow-y:auto;width:100%; color:#555555;margin-right:0 5px" >
           <table>
            <tr>
              <td ><div style="padding-bottom:5px;margin-right:5px;font-weight: bold;border-bottom:5px solid <?php echo $borderColor;?>40"><?php echo $msg->name;?></div></td>
            </tr>
            <tr>
              <td style="padding-top:5px;padding-right:5px;"><?php echo htmlEncode($msg->description, 'formatted');?></td>
            </tr>
           </table>
          </div>
           <?php 
           if ($cpt>0) echo '<div style="position:absolute;top:-23px;left:100px;opacity:30%" class="imageColorNewGui dijitButtonIcon dijitButtonIconPrevious"> </div>';
           if ($cpt < count($listMsg)-1) echo '<div style="position:absolute;top:-23px;right:100px;opacity:30%" class="imageColorNewGui dijitButtonIcon dijitButtonIconNext"> </div>';
           ?>
        </div>
         <?php
        //}
        $cpt++;
      }
      
    }
    ?>
    
    </div>
    <?php 
}

function showProjects($refreshTab=false, $showAllProject=null) {
global $cptMax, $print, $workVisibility, $templateProjectList, $arrayCols, $showCol, $cptCol,$tabShowTodaySection;
  if(!$refreshTab){
    echo '<div onMouseOver="dojo.byId(\'hideProjects\').style.display=\'block\';dojo.byId(\'fullscreenProjects\').style.display=\'block\';" onMouseOut="dojo.byId(\'hideProjects\').style.display=\'none\';dojo.byId(\'fullscreenProjects\').style.display=\'none\';">';
    echo '  <table style="width:100%;"><tr>';
    echo '   <td class="simple-grid__header">'.i18n('menuProject').'</td>';
    echo '   <td style="float:right;">';   
    
    echo '<div style = "display: flex; gap: 10px;">';
    echo '<span title="'.i18n('enlargeThisBlock').'" id="fullscreenProjects" class="roundedButtonSmall noRotate" style="opacity:40%;width:24px;position:relative;top:2px;float:right;display:none;">';
    echo '<div id="fullscreenProjectsIcon" class="iconButton  iconFullScreen iconSize22 noRotate" onClick="toggleFullscreenProjectsDiv();"></div>';
    echo "</span>";
    echo '<div title="'.i18n('hideDivToday').'" id="hideProjects" style="opacity:40%;width:24px;position:relative;top:2px;float:right;display:none;">';
    $image='../view/css/images/tabClose.svg';
    echo '<img class="roundedButtonSmall  iconSize22" src="'.$image.'" onClick="hideDivToday(\'showProjects\');setTodayParameterHideSection(\'Projects\');" />';
    echo "</div>";
    
    echo '</div>';
    
    $notDisplay = true;
    if(!$notDisplay){
      ?>
           <button title="<?php echo i18n('parameter')?>"  
                 dojoType="dijit.form.Button" 
                 id="paramButtonProject" name="paramButtonProject"
                 iconClass="dijitButtonIcon dijitButtonIconTool" class="detailButton" showLabel="false">
                 <script type="dojo/method" event="onClick" args="evt">
                    showInfo('<?php echo i18n('featureNotAvailable');?>');
                 </script>
         </button>
         <button title="<?php echo i18n('print')?>"  
                 dojoType="dijit.form.Button" 
                 id="printButtonroject" name="printButtonroject"
                 iconClass="dijitButtonIcon dijitButtonIconPrint" class="detailButton" showLabel="false">
                 <script type="dojo/method" event="onClick" args="evt">
                    showInfo('<?php echo i18n('featureNotAvailable');?>');
                 </script>
         </button>
         <button title="<?php echo i18n('reportPrintPdf')?>"  
                 dojoType="dijit.form.Button" 
                 id="printButtonPdfroject" name="printButtonPdfroject"
                 iconClass="dijitButtonIcon dijitButtonIconPdf" class="detailButton" showLabel="false">
                 <script type="dojo/method" event="onClick" args="evt">
                     showInfo('<?php echo i18n('featureNotAvailable');?>');
                 </script>
         </button> 
      <?php
      }
      echo '    </td>';
      echo '  </tr>';
      echo '  </table>';
      echo '</div>';
  }
  
  $user=getSessionUser();
  $parmSizeProject=Parameter::getUserParameter('sizeDisplayProjectToday');
  if (!$parmSizeProject) $parmSizeProject=$cptMax;
  $prjVisLst=$user->getVisibleProjects();
  $prjLst=$user->getHierarchicalViewOfVisibleProjects(true);
  $lstProj=array();
  foreach ($prjLst as $idProject=>$p){ 
    $type=SqlList::getFieldFromId('Project',pq_trim($idProject,"#"),'idProjectType');
    $codeType=SqlList::getFieldFromId('ProjectType',$type,'code');
    if ($codeType=='TMP' or $codeType=='ADM') unset($prjLst[$idProject]);
    else $lstProj[]=pq_substr($idProject,1);
  }
  if(!$showAllProject and sessionValueExists('showAllProjectTodayVal')){
    $showAllProject=getSessionValue('showAllProjectTodayVal');
  }else if(!$showAllProject and RequestHandler::isCodeSet('showAllProjectToday')){
    $showAllProject=RequestHandler::getValue('showAllProjectToday');
  }else if(!$showAllProject){
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
  $selectedTab=Parameter::getUserParameter('todayProjectTab');
  if (! $selectedTab) $selectedTab='meteo';
  $projectViewType="";
  if(!$refreshTab){
  ?>
  <div style="width:100%;height:100%;">
      <input id="showAllProjectToday" name="showAllProjectToday"  hidden value="<?php echo $showAllProject;?>" />
      <div dojoType="dijit/layout/TabContainer" id="todayTab" class="" style="height:95%;min-width:850px;min-height:250px;max-height:258px;">
<?php 
// ==================================================================
// Projects / Meteo
// ==================================================================
?>
     <div id="todayMeteoTab" style="overflow:hidden" onShow="saveUserParameter('todayProjectTab','meteo');" class="transparentBackground" style="overflow:hidden;backgound-color:transparent !important" data-dojo-type="dijit/layout/ContentPane" title="<img src='../view/css/images/iconWeather.png' style='width:32px;height:32px;position:absolute;top:2px;'/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<?php echo i18n('weather');?>" <?php if ($selectedTab=='meteo') echo 'data-dojo-props="selected:true"';?> >  
         <?php
   }
   if(!$refreshTab or $refreshTab == "Meteo"){
   	 $projectViewType="Meteo";
     if (count($prjLst)==0) {
       echo '<div class="todayData" style="width:90%;text-align:center;font-style:italic;color:#A0A0A0">'.i18n('noDataToDisplay').'</div>';
     }
    if ($showOne and count($prjLst)>0) {
      
      $width=($print)?'45':'35';
      $widthProj=300;
      $lstProj=implode(",",$lstProj);
      echo '<table class="tranparent" align="left" xstyle="width:850px;max-width:850px;">';
      echo '<tr style="height:32px">';
      echo '<td style="width:'.($widthProj).'px;">&nbsp;</td>';
    if ($showProject) {
      echo '<td class="todayData" style="width:30px;" title="'.i18n("Health").'"><div style="margin: 0 auto;" class="iconHealth imageColorNewGui iconSize22"></div></td>';
      echo '<td class="todayData" style="width:30px" title="'.i18n("Quality").'"><div  style="margin: 0 auto;" class="iconQuality imageColorNewGui iconSize22"></div></td>';
      echo '<td class="todayData" style="width:30px" title="'.i18n("Trend").'"><div  style="margin: 0 auto;" class="iconTrend imageColorNewGui iconSize22  "></div></td>';
      echo '<td class="todayData" style="width:90px" title="'.pq_ucfirst(i18n("colProgress")).'"><div  style="margin: 0 auto;" class="iconOverallProgress imageColorNewGui iconSize22  "></div></td>';
      echo '<td class="todayData" >&nbsp;</td>';
    }
    echo '</tr>';
    echo '</table>';
   echo '<div id="meteoDivScroll" style="clear: left;min-width:850px;height: 185px; ';
    echo ' overflow-y:auto; overflow-x:hidden;" onscroll="dojo.byId(\'elementsDivScroll\').scrollTop=this.scrollTop;dojo.byId(\'datesDivScroll\').scrollTop=this.scrollTop;">';
   echo '<table class="tranparent" align="left" xstyle="width:850px;max-width:850px;">';
    $cpt=0;
    $countPro=-1;
    $levels=array();

    foreach ($prjLst as $sharpid=>$sharpName) {
      $cpt++;
      $visibleRows=array();
      $countPro++;
      if($parmSizeProject!='' and $parmSizeProject==$countPro and $showAllProject=='false'){
        echo '<tr style="text-align: center;font-weight:bold;"><td colspan="6"  class="messageData"><div >'.i18n('limitedDisplay', array($parmSizeProject)).'</div><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconDisplayMore16" onclick="refreshTodayProjectsList(\''.$projectViewType.'\',\'true\')" title="'.i18n('displayMore').'" >&nbsp;</div></td></tr>';
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
      if (pq_strpos($wbs,'.')===false) $showForced=true;
      $display=true;
      if($colParent->id=="" and count($isSubProj)!=0 and  $showForced==false){
        $display=false;
        //continue;
      }
      if($hiddenSubProj ){
        $class="ganttExpandOpened";
      }else{
        $class="ganttExpandClosed";
      }
      //
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
        //start TABLE tr
        
        echo '<tr style="text-align: center;height:36px;'.(($display)?'':'display:none;').'" id="projRow_'.$idProj.'">';
        echo '  <td class="" style="text-align-left;border-right:0;">';
        echo '  <div class="dataContent" style="width:'.$widthProj.'px;position:relative;top:-3px"><div class="dataExtend" style="min-width:'.($widthProj-5).'px">';
        echo '<div style="float:left;">'.$tab.'</div>';
        if($subProj and !$print){
          echo '     <input id="group_asSub_'.$idProj.'" hidden value="'.implode(',', $listSub).'">';
          echo '     <div id="group_'.$idProj.'" class="'.$class.'"';
          echo '      style="float:left; width:16px; height:13px;top:3px"';
          echo '      onclick="expandProjectInToDay(\''.$idProj.'\',\''.implode(",", $listSub).'\',\''.implode(',', $visibleRows).'\',\'todayDateTab\');">&nbsp;&nbsp;&nbsp;&nbsp;</div>';
        }else{
          echo '     <div id="group_'.$idProj.'"';
          echo '      style="float:left; width:16px; height:13px;top:3px;position:relative;"';
          echo '     ><div style="border:1px solid #cccccc;width:10px;height:10px;position:relative;border-radius:2px;top:0px;left:0px">&nbsp;</div></div>';
        }
        echo '<div '.$goto.' style="width:100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; " class="'.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'">'.htmlEncode($name);
        echo '</div>';
        echo '</div/</div>';
        echo '</td>';
        if ($showProject) {
          $extraStyle="width:22px;";
          $extraStyleImg="width:22px; height:22px;";
          $extraStyleColor="margin-left:5px;width:22px; height:22px;border-radius:12px;";
          //$extraStyle.="border: 1px solid green;";
          if ($healthIcon) {
            echo ' <td class="todayData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:50px;vertical-align:middle;'.$extraStyle.'" '.$goto.' >'.'<img style="'.$extraStyleImg.'" src="icons/'.$healthIcon.'" title="'.$healthName.'"/>'.'  </td>';
          } else {
            echo '  <td class="todayData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:50px;'.$extraStyle.'" '.$goto.' >'.'    <div class="colorHealth" style="'.$styleHealth.$extraStyleColor.'background:'.$healthColor.';" title="'.$healthName.'">&nbsp;</div>'.'  </td>';
          }
          if ($qualityIcon) {
            echo ' <td class="todayData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:50px;vertical-align:middle;'.$extraStyle.'" '.$goto.' >'.(($qualityIcon)?'<img height="12px" style="'.$extraStyleImg.'" src="icons/'.$qualityIcon.'" title="'.$qualityName.'"/>':'').'  </td>';
          } else {
            echo '  <td class="todayData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:50px;'.$extraStyle.'" '.$goto.' >'.'    <div class="colorHealth" style="'.$styleHealth.$extraStyleColor.'background:'.$qualityColor.';" title="'.$qualityName.'">&nbsp;</div>'.'  </td>';
          }
          if ($trendIcon) {
            echo ' <td class="todayData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:50px;vertical-align:middle;'.$extraStyle.'" '.$goto.' >'.(($trendIcon)?'<img height="12px" style="'.$extraStyleImg.'" src="icons/'.$trendIcon.'" title="'.$trendName.'"/>':'').'  </td>';
          } else {
            echo '  <td class="todayData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:50px;'.$extraStyle.'" '.$goto.' >'.'    <div class="colorHealth" style="'.$styleHealth.$extraStyleColor.'background:'.$trendColor.';" title="'.$healthName.'">&nbsp;</div>'.'  </td>';
          }
          echo '<td class="todayData" style="width:100px;">'.progressFormatter($progress,"").'</td>';
          echo '<td class="todayData">&nbsp;</td>';
        }
        echo '</tr>';
      }
    }
    if($showAllProject=='true'){
      echo '<tr style="text-align: center;font-weight:bold;"><td colspan="18"  class="messageData"><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconReduceDisplay16" onclick="refreshTodayProjectsList(\''.$projectViewType.'\',\'false\')" title="'.i18n('reduceDisplayToday').'">&nbsp;</div></td></tr>';
    }
    echo '</table>';
    echo '</div>';
  } ?> 
        </div>
<?php }?>
<?php $projectViewType="";?>
<?php 
// ==================================================================
// Projects / Elements
// ==================================================================
?>
 <?php 
 if(!$refreshTab){?>
        <div id="todayElementTab" style="overflow:hidden" class="transparentBackground" onShow="saveUserParameter('todayProjectTab','element');" data-dojo-type="dijit/layout/ContentPane" title="<img src='../view/css/images/iconSituation.png' style='width:26px;height:26px;position:absolute;top:4px;'/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<?php echo i18n('element');?>" <?php if ($selectedTab=='element') echo 'data-dojo-props="selected:true"';?>> 
 <?php
  }
 if(!$refreshTab or $refreshTab == "Element"){
      $projectViewType="Element";
      if (count($prjLst)==0) {
        echo '<div class="todayData" style="width:90%;text-align:center;font-style:italic;color:#A0A0A0">'.i18n('noDataToDisplay').'</div>';
      } 
      if ($showOne and count($prjLst)>0) {
      echo '<div class="tranparent" style="width:100%; overflow-x:auto" >';
      $width=($print)?'50':'55';
      $widthProj=300;
      echo '<table class="tranparent" align="left" xstyle="width:850px;">';
      echo '<tr style="height:32px">';
      echo '<td style="width:'.($widthProj).'px;min-width:'.($widthProj).'px;max-width:'.($widthProj).'px;">&nbsp;</td>';
      foreach ($arrayCols as $col) {
        if (!$showCol[$col]) continue;
        echo '  <td class="todayData" style="margin:0;padding:0;width:'.$width.'px;max-width:'.$width.'px;text-align:center"><div style="margin: 0 auto; width:22px;text-align:center;text-overflow: hidden;">'.formatIcon($col, 22, i18n('menu'.$col)).'</div></td>'; 
      }
      echo '<td class="todayData" >&nbsp;</td>';
      echo '</tr>';
      echo '</table>';
      echo '<div id="elementsDivScroll" style="clear: left;min-width:850px; height: 185px;';
      echo 'overflow-y:auto; overflow-x:hidden;" onscroll="dojo.byId(\'meteoDivScroll\').scrollTop=this.scrollTop;dojo.byId(\'datesDivScroll\').scrollTop=this.scrollTop;">';
       echo '<table class="tranparent" align="left" xstyle="width:850px;">';
      $cpt=0;
      $countPro=-1;
      $levels=array();
    foreach ($prjLst as $sharpid=>$sharpName) {
      $cpt++;
      $visibleRows=array();
      $countPro++;
      if($parmSizeProject!='' and $parmSizeProject==$countPro and $showAllProject=='false'){
        echo '<tr style="text-align: center;font-weight:bold;"><td colspan="18"  class="messageData"><div >'.i18n('limitedDisplay', array($parmSizeProject)).'</div><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconDisplayMore16" onclick="refreshTodayProjectsList(\''.$projectViewType.'\',\'true\')" title="'.i18n('displayMore').'" >&nbsp;</div></td></tr>';
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
        if(is_array($lstProj))$lstProj=implode(',', $lstProj);
        $pose=pq_trim(pq_strpos($lstProj,$isSubProj[0]));
      }
      if($pose==''){
        $showForced=true;
      }
      if (pq_strpos($wbs,'.')===false) $showForced=true;
      $display=true;
      if($colParent->id=="" and count($isSubProj)!=0 and  $showForced==false){
        $display=false;
        //continue;
      }
      if($hiddenSubProj ){
        $class="ganttExpandOpened";
      }else{
        $class="ganttExpandClosed";
      }
      //
      foreach ($arrayCols as $col) {
        $nbItem[$col]=countFrom($cptCol[$col], $id, '', $countScope);
        $nbItemAll[$col]=countFrom($cptCol[$col], $id, 'All', $countScope);
        $nbItemTodo[$col]=countFrom($cptCol[$col], $id, 'Todo', $countScope);
        $nbItemDone[$col]=countFrom($cptCol[$col], $id, 'Done', $countScope);
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
        //start TABLE tr
        echo '<tr style="text-align: center;height:36px;'.(($display)?'':'display:none;').'" id="el_projRow_'.$idProj.'">';
        echo '  <td class="" style="border-right:0">';
        echo '  <div class="dataContent" style="width:'.$widthProj.'px;position:relative;top:-3px"><div class="dataExtend" style="min-width:'.($widthProj-5).'px">';
        echo '<div style="float:left;">'.$tab.'</div>';
        if($subProj and !$print){
          echo '     <input id="el_group_asSub_'.$idProj.'" hidden value="'.implode(',', $listSub).'">';
          echo '     <div id="el_group_'.$idProj.'" class="'.$class.'"';
          echo '      style="float:left; width:16px; height:13px;top:3px"';
          echo '      onclick="expandProjectInToDay(\''.$idProj.'\',\''.implode(",", $listSub).'\',\''.implode(',', $visibleRows).'\',\'todayElementTab\');">&nbsp;&nbsp;&nbsp;&nbsp;</div>';
        }else{
          echo '     <div id="el_group_'.$idProj.'"';
          echo '      style="float:left; width:16px; height:13px;top:3px;position:relative;"';
          echo '     ><div style="border:1px solid #cccccc;width:10px;height:10px;position:relative;border-radius:2px;top:0px;left:0px">&nbsp;</div></div>';
        }
        echo '<div '.$goto.' style="width:100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; " class="'.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'">'.htmlEncode($name);
        echo '</div></td>';
        foreach ($arrayCols as $col) {
          if (!$showCol[$col]) continue;
          echo '  <td style="width:'.$width.'px" class="todayData '.($show?'':'Grey').' colorNameData" onclick=\'gotoElement("'.$col.'",null);stockHistory("'.$col.'",null,"object");setSelectedProject("'.htmlEnCode($proj->id).'","'.htmlEnCode($proj->name).'","selectedProject");\' style="cursor: pointer;">'.($show?displayProgress($nbItem[$col], $nbItemAll[$col], $nbItemTodo[$col], $nbItemDone[$col]):'').'</td>';
        }
        echo '</tr>';
      }
    }
    if($showAllProject=='true'){
      echo '<tr style="text-align: center;font-weight:bold;"><td colspan="18"  class="messageData"><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconReduceDisplay16" onclick="refreshTodayProjectsList(\''.$projectViewType.'\',\'false\')" title="'.i18n('reduceDisplayToday').'">&nbsp;</div></td></tr>';
    }
    echo '</table>';
    echo '</div>';
    echo '</div>';
  } ?> 
        </div>
<?php }?>
<?php $projectViewType="";?>
<?php if(!$refreshTab){
// ==================================================================
// Projects / Dates
// ==================================================================
?>
    <div id="todayDateTab" style="overflow:hidden" class="transparentBackground" onShow="saveUserParameter('todayProjectTab','date');" data-dojo-type="dijit/layout/ContentPane" title="<img src='../view/css/images/iconOverallProgress32.png' style='width:26px;height:26px;position:absolute;top:4px;'/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<?php echo i18n('dateandperiod');?>" <?php if ($selectedTab=='date') echo 'data-dojo-props="selected:true"';?>>  
    <?php
      }
  if(!$refreshTab or $refreshTab == "Date"){
    $projectViewType="Date";
    if (count($prjLst)==0) {
      echo '<div class="todayData" style="width:90%;text-align:center;font-style:italic;color:#A0A0A0">'.i18n('noDataToDisplay').'</div>';
    }
    if ($showOne and count($prjLst)>0) {
     echo '<div class="tranparent" style="width:100%; height:100%;overflow: hidden" >';
      $width=($print)?'50':'55';
      $widthRealEstimated = '135';
      $widthProj=300;
      echo '<table class="tranparent" align="left" xstyle="width:850px;">';
      echo '<tr style="height:32px">';
      echo '<td style="width:'.($widthProj).'px;min-width:'.($widthProj).'px;max-width:'.($widthProj).'px;">&nbsp;</td>';
 
    
//     if ($showProject) echo '  <td  class="todayData" style="margin:0;padding:0;width:'.($width*3).'px;max-width:'.($width*3).'px;text-align:center">'
//                           .'<div style="border-bottom:1px solid #E0E0E0;width:'.($width*3-6).'px;left:3px; overflow: hidden; text-overflow: hidden;">'.pq_ucfirst(i18n('progress')).'</div>'
//                           .'<table style="width:100%;font-size:75%"><tr><td style="width:33%">'.i18n('colReal').'</td><td style="width:34%">'.i18n('colExpected').'</td><td style="width:33%">'.i18n('colEstimated').'</td></tr></table>'
//                           .'</td>';
      if ($showProject) echo '  <td  class="todayData" style="margin:0;padding:0;width:'.($widthRealEstimated).'px;max-width:'.($widthRealEstimated).'px;text-align:center">'
      .'<div style="border-bottom:1px solid #E0E0E0;width:'.($widthRealEstimated-6).'px;left:3px; overflow: hidden; text-overflow: hidden;">'.pq_ucfirst(i18n('progress')).'</div>'
                          .'<table style="width:100%;font-size:75%"><tr><td style="width:40%">'.i18n('colReal').'</td><td style="width:60%">'.i18n('colEstimated').'</td></tr></table>'
                          .'</td>';
    
    if ($workVisibility=='ALL' and $showProject) {
      echo '  <td class="todayData" style="margin:0;padding:0;width:'.($width*3).'px;max-width:'.($width*3).'px;text-align:center">'
          .'<div style="border-bottom:1px solid #E0E0E0;width:'.($width*3-6).'px;left:3px; overflow: hidden; text-overflow: hidden;">'.pq_ucfirst(i18n('colWork')).'</div>'
          .'<table style="width:100%;font-size:75%"><tr><td style="width:33%">'.i18n('colValidated').'</td><td style="width:34%">'.i18n('colReal').'</td><td style="width:33%">'.i18n('colLeft').'</td></tr></table>'
          .'</td>';
      echo '  <td class="todayData" style="margin:0;padding:0;width:'.$width.'px;max-width:'.$width.'px;text-align:center"><div style="width:'.($width).'px; overflow: hidden; text-overflow: hidden;">'.pq_ucfirst(i18n('colMargin')).'</div></td>';
    }
    if ($showProject) echo '  <td class="todayData" style="margin:0;padding:0;width:'.($width*1.5).'px;max-width:'.($width*1.5).'px;text-align:center"><div style="width:'.($width*1.5).'px; overflow: hidden; text-overflow: hidden;">'.pq_ucfirst(i18n('colEndDate')).'</div></td>'
        .'  <td class="todayData" style="margin:0;padding:0;width:'.$width.'px;max-width:'.$width.'px;text-align:center"><div style="width:'.($width).'px; overflow: hidden; text-overflow: hidden;">'.pq_ucfirst(i18n('colLate')).'</div></td>';
    echo '</tr>';
    echo '</table>';
    echo '<div id="datesDivScroll" style="clear: left;min-width:850px; height: 185px;';
    echo 'overflow-y:auto; overflow-x:hidden;" onscroll="dojo.byId(\'meteoDivScroll\').scrollTop=this.scrollTop;dojo.byId(\'elementsDivScroll\').scrollTop=this.scrollTop;">';
  echo '<table class="tranparent" align="left" xstyle="width:850px;">';
    $cpt=0;
    $countPro=-1;
    $levels=array();
    foreach ($prjLst as $sharpid=>$sharpName) {      
      $cpt++;
      $visibleRows=array();
      $countPro++;
      if($parmSizeProject!='' and $parmSizeProject==$countPro and $showAllProject=='false'){
        echo '<tr style="text-align: center;font-weight:bold;"><td colspan="18"  class="messageData"><div >'.i18n('limitedDisplay', array($parmSizeProject)).'</div><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconDisplayMore16" onclick="refreshTodayProjectsList(\''.$projectViewType.'\',\'true\')" title="'.i18n('displayMore').'" >&nbsp;</div></td></tr>';
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
        if(is_array($lstProj))$lstProj=implode(',', $lstProj);
        $pose=pq_trim(pq_strpos($lstProj,$isSubProj[0]));
      }
      if($pose==''){
        $showForced=true;
      }
      if (pq_strpos($wbs,'.')===false) $showForced=true;
      $display=true;
      if($colParent->id=="" and count($isSubProj)!=0 and  $showForced==false){
        $display=false;
        //continue;
      }
      if($hiddenSubProj ){
        $class="ganttExpandOpened";
      }else{
        $class="ganttExpandClosed";
      }
      //
      $prjPE=SqlElement::getSingleSqlElementFromCriteria('ProjectPlanningElement', array('refType'=>'Project', 'refId'=>$id));
      $endDate=$prjPE->plannedEndDate;
      $endDate=($endDate=='')?$prjPE->validatedEndDate:$endDate;
      $endDate=($endDate=='')?$prjPE->initialEndDate:$endDate;
      $progress='0';
      $expectedProgress='0';
      if ($prjPE->realWork!='' and $prjPE->plannedWork!='' and $prjPE->plannedWork!='0') {
        $progress=$prjPE->progress;
        $expectedProgress=$prjPE->expectedProgress;
      }
      $real=$prjPE->realWork;
      $left=$prjPE->leftWork;
      $validated=$prjPE->validatedWork;
      $expected=($validated-$real);
      $realUnit=Work::displayWork($real);
      $leftUnit=Work::displayWork($left);
      $validatedUnit=Work::displayWork($validated);
      $expectedUnit=Work::displayWork($expected);
      if ($realUnit>99 or $leftUnit>99 or $validatedUnit>99) {
        $realUnit=ceil($realUnit);
        $leftUnit=ceil($leftUnit);
        $validatedUnit=ceil($validatedUnit);
        $expectedUnit=ceil($expectedUnit);
      }
      $realDisp=pq_str_replace(array(' ','&nbsp;'),'',Work::displayWorkWithUnit(Work::convertWork($realUnit)));
      $leftDisp=pq_str_replace(array(' ','&nbsp;'),'',Work::displayWorkWithUnit(Work::convertWork($leftUnit)));
      $validatedDisp=pq_str_replace(array(' ','&nbsp;'),'',Work::displayWorkWithUnit(Work::convertWork($validatedUnit)));
      $expectedDisp=pq_str_replace(array(' ','&nbsp;'),'',Work::displayWorkWithUnit(Work::convertWork($expectedUnit)));
      $margin=$prjPE->marginWorkPct;
      if ($margin!==null) {
        $colorMargin=($margin==0)?'#555555':(($margin<0)?'#DD0000':'#00AA00');
        if (abs($margin)>999) {
          if (abs($margin)>9999) {
            $margin=($margin>0)?'>999':'<999';
          } else {
            $margin=round($margin/10,0);
          }
          $margin='<div style="color:'.$colorMargin.';">'.$margin.'&#8240;</div>';
        } else {
          $margin='<div style="color:'.$colorMargin.';">'.$margin.'%</div>';
        }
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
        echo '<tr style="text-align: center;height:36px;'.(($display)?'':'display:none;').'" id="dt_projRow_'.$idProj.'">';
        echo '  <td class="" style="border-right:0">';
        echo '  <div class="dataContent" style="width:'.$widthProj.'px;position:relative;top:-3px"><div class="dataExtend" style="min-width:'.($widthProj-5).'px">';
        echo '<div style="float:left;">'.$tab.'</div>';
        if($subProj and !$print){
          echo '     <input id="dt_group_asSub_'.$idProj.'" hidden value="'.implode(',', $listSub).'">';
          echo '     <div id="dt_group_'.$idProj.'" class="'.$class.'"';
          echo '      style="float:left; width:16px; height:13px;top:3px"';
          echo '      onclick="expandProjectInToDay(\''.$idProj.'\',\''.implode(",", $listSub).'\',\''.implode(',', $visibleRows).'\',\'todayDateTab\');">&nbsp;&nbsp;&nbsp;&nbsp;</div>';
        }else{
          echo '     <div id="dt_group_'.$idProj.'"';
          echo '      style="float:left; width:16px; height:13px;top:3px;position:relative;"';
          echo '     ><div style="border:1px solid #cccccc;width:10px;height:10px;position:relative;border-radius:2px;top:0px;left:0px">&nbsp;</div></div>';
        }
        echo '<div '.$goto.' style="width:100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; " class="'.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'">'.htmlEncode($name);
        echo '</div></td>';
        if ($showProject) echo '  <td style="width:'.$width.'px;max-width:'.$width.'px;" class="todayData'.($show?'':'Grey').' colorNameData">'.($show?displayProgress(htmlDisplayPct($progress), $planned, $left, $real, true, true):'').'</td>';
        //if ($showProject) echo '  <td style="width:'.$width.'px" class="todayData'.($show?'':'Grey').' colorNameData">'.($show?displayProgress(htmlDisplayPct($expectedProgress), $validated, $expected, $real, true, true):'').'</td>';
        $widthEstimated = 75; 
        if ($showProject) echo '  <td style="margin:0;padding:0;width:'.$widthEstimated.'px;max-width:'.$widthEstimated.'px;"  class="todayData '.($show?'':'Grey').'"><div style="width:'.($widthEstimated).'px; overflow: hidden;overflow-wrap: break-word;word-break: break-word; text-overflow: hidden;">'.($show?SqlList::getNameFromId('OverallProgress', $proj->idOverallProgress):"").'</div></td>';
        if ($workVisibility=='ALL' and $showProject) {
          echo '  <td style="margin:0;padding:0;width:'.$width.'px;max-width:'.$width.'px;" class="todayData'.($show?'':'Grey').'">'.($show?$validatedDisp:'').'</td>';
          echo '  <td style="margin:0;padding:0;width:'.$width.'px;max-width:'.$width.'px;" class="todayData'.($show?'':'Grey').'">'.($show?$realDisp:'').'</td>';
          echo '  <td style="margin:0;padding:0;width:'.$width.'px;max-width:'.$width.'px;" class="todayData'.($show?'':'Grey').'">'.($show?$leftDisp:'').'</td>';
         echo '  <td style="margin:0;padding:0;width:'.$width.'px;max-width:'.$width.'px;" class="todayData'.($show?'':'Grey').'">'.($show?$margin:'').'</td>';
        }
        if ($showProject) echo '  <td  style="margin:0;padding:0;width:'.($width*1.5).'px;max-width:'.($width*1.5).'px;" class="todayData '.($show?'':'Grey').'" NOWRAP>'.($show?htmlFormatDate($endDate):'').'</td>'
            .'  <td style="margin:0;padding:0;width:'.$width.'px;max-width:'.$width.'px;" class="todayData'.($show?'':'Grey').'">'.($show?$late:'').'</td>';
        echo "<td>&nbsp;</td>";
        echo '</tr>';
      }
    }
    if($showAllProject=='true'){
      echo '<tr style="text-align: center;font-weight:bold;"><td colspan="18"  class="messageData"><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconReduceDisplay16" onclick="refreshTodayProjectsList(\''.$projectViewType.'\',\'false\')" title="'.i18n('reduceDisplayToday').'">&nbsp;</div></td></tr>';
    }
    echo '</table>';
    echo '</div>';
    echo '</div>';
  } ?> 
        </div>
<?php }?>
<?php 
// ==================================================================
// Projects / End
// ==================================================================

?>        
      </div>
   </div>
   <?php 
  
  
}

function showDocuments() {
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
  showActivitiesList($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_DocumentDiv', 'documentsApproval');
}

function countFrom($list, $idProj, $type, $scope) {
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

function displayProgress($value, $allValue, $todoValue, $doneValue, $showTitle=true, $isWork=false) {
  global $cptDisplayId, $print, $workVisibility;
  if (!$workVisibility) {
    $pe=new ProjectPlanningElement();
    $pe->setVisibility();
    $workVisibility=$pe->_workVisibility;
  }
  if ($value==='') {
    return $value;
  }
  $width=($print)?'46':'51';

  $green=($allValue!=0 and $allValue)?round($width*($allValue-$todoValue)/$allValue, 0):$width;
  $red=$width-$green;
  
  $cptDisplayId+=1;
  $result='<div style="margin-left:2px;position:relative; height:100%;width:'.$width.'px" id="displayProgress_'.$cptDisplayId.'">';
  $result.='<div style="overflow:hidden;position:absolute; height:4px;top:24px;left:0px; width:'.$green.'px;background: #AAFFAA;">&nbsp;</div>';
  $result.='<div style="position:absolute; width:'.$red.'px;height:4px;top:24px;left:'.$green.'px;background: #FFAAAA;">&nbsp;</div>';
  $result.='<div style="position:relative;top:8px;width:100%;text-align:center;background:#F0F0F0A0">'.$value.'</div>';
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

function showAssignedTasks() {
  if (!securityCheckDisplayMenu(null, 'Activity') and !securityCheckDisplayMenu(null, 'Meeting') ) return;
  $user=getSessionUser();
  $ass=new Assignment();
  $act=new Activity();
  $meet=new Meeting();
  $poker = new PokerSession();
  $whereNoAdmin=" and idProject not in ".Project::getAdminitrativeProjectList();
  $where="1=0";
  $whereTicket=$where;
  $whereDocument=$where;
  $whereActivity=" (exists (select 'x' from ".$ass->getDatabaseTableName()." x "."where x.refType='Activity' and x.refId=".$act->getDatabaseTableName().".id and x.idResource=".Sql::fmtId($user->id).")".") and idle=0 and done=0 and paused=0".$whereNoAdmin;
  $whereMeeting=pq_str_replace(array('Activity', $act->getDatabaseTableName(), 'and paused=0'), array('Meeting', $meet->getDatabaseTableName(), ''), $whereActivity);
  $whereDecision=$where;
  $wherePokerSession = " (exists (select 'x' from ".$ass->getDatabaseTableName()." x "."where x.refType='PokerSession' and x.refId=".$poker->getDatabaseTableName().".id and x.idResource=".Sql::fmtId($user->id).")".") and idle=0 and done=0".$whereNoAdmin;
  showActivitiesList($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision,$wherePokerSession, 'Today_WorkDiv', 'todayAssignedTasks');
}

function showAccountableTasks() {
  //if (!getSessionUser()->isResource) return;
  $user=getSessionUser();
  $where="1=0";
  $whereNoAdmin=" and idProject not in ".Project::getAdminitrativeProjectList();
  $whereTicket="idAccountable='".Sql::fmtId($user->id)."' and idle=0 and done=0".$whereNoAdmin;
  $whereActivity=$where;
  $whereMeeting=$whereActivity;
  $whereDocument=$whereMeeting;
  $whereDecision=$where;
  $wherePokerSession=$where;
  showActivitiesList($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_AccDiv', 'todayAccountableTasks');
}

function showResponsibleTasks() {
  //if (!getSessionUser()->isResource) return;
  $user=getSessionUser();
  $ass=new Assignment();
  $act=new Activity();
  $whereNoAdmin=" and idProject not in ".Project::getAdminitrativeProjectList();
  $where="(idResource=".Sql::fmtId($user->id).") and idle=0 and done=0".$whereNoAdmin;
  $whereTicket=$where." and paused=0";
  $whereActivity=$where." and paused=0";
  $whereMeeting=$where;
  $whereDocument="1=0";
  $whereDecision=$whereDocument;
  $wherePokerSession=$where;
  showActivitiesList($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_RespDiv', 'todayResponsibleTasks');
}

function showIssuerRequestorTasks() {
  $user=getSessionUser();
  $whereNoAdmin=" and idProject not in ".Project::getAdminitrativeProjectList();
  $where="(idUser='".Sql::fmtId($user->id)."'".") and idle=0 and done=0".$whereNoAdmin;
  $whereTicket="(idUser='".Sql::fmtId($user->id)."'"." or idContact='".Sql::fmtId($user->id)."'".") and idle=0 and done=0 and paused=0".$whereNoAdmin;
  $whereActivity=$whereTicket;
  $whereMeeting=$where;
  $whereDocument="1=0";
  $whereDecision=$whereDocument;
  $wherePokerSession=$where;
  showActivitiesList($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_FollowDiv', 'todayIssuerRequestorTasks');
}

function showProjectsTasks() {
  $where="(idProject in ".getVisibleProjectsList().") and idle=0 and done=0";
  $whereTicket=$where;
  $whereActivity=$where;
  $whereMeeting=$where;
  $whereDocument="1=0";
  $whereDecision=$whereDocument;
  $wherePokerSession=$where;
  showActivitiesList($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument,$whereDecision, $wherePokerSession,'Today_ProjectTasks', 'todayProjectsTasks');
}

function showActivitiesList($where, $whereActivity, $whereTicket, $whereMeeting, $whereDocument, $whereDecision, $wherePokerSession, $divName, $title) {
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
  if ($showAllToday=='true') $cptMax=99999;
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
  
  //table todo
  echo '<div onMouseOver="dojo.byId(\'hideTodoDiv\').style.display=\'block\';" onMouseOut="dojo.byId(\'hideTodoDiv\').style.display=\'none\';">';
  echo '  <table style="width:100%">';
  echo '   <tr><td class="simple-grid__header" style="width:25%">'.i18n('todoToday').'</td><td style="width:50%;text-align:center;" class="simple-grid__headerSubtitle">'.i18n($title).'</td>';
  echo ' <td style="width:25%">  <div  title="'.i18n('hideDivToday').'" id="hideTodoDiv" style="opacity:40%;display:none;width:24px;position:absolute;top:30px;right:30px;float:right;">';
  $image='../view/css/images/tabClose.svg';
  echo '<img class="roundedButtonSmall  iconSize22" src="'.$image.'" onClick="hideDivToday(\'hideTodo\');setTodayParameterHideSection(\'Todo\');" />';
  echo '</div></td></tr>';
  echo '   <tr><td colspan="2">&nbsp;</td></tr>';
  echo '  </table>';
  echo '</div>';
  
  if (!$print or !pq_array_key_exists($divName, $collapsedList)) {
    echo '<input id="showAll'.$showAllLib.'Today" name="showAll'.$showAllLib.'Today"  hidden value="'.$showAllToday.'" />';
    echo '<form id="today'.$showAllLib.'Form" name="today'.$showAllLib.'Form" style="max-height:230px;overflow-y:auto">';
    echo '<table align="center" style="width:99%;padding-right:20px;">';
    $cpt=0;
    $listEcheance=array();
    if (count($list)==0) echo '<tr><td colspan="2" class="todayData" style="text-align:center;font-style:italic;color:#A0A0A0">'.i18n('noDataToDisplay').'</td></tr>';
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
      $color="background-color:transparent";
      if ($alertLevel=='ALERT') {
        $color='background-color:#FFAAAA80;';
      } else if ($alertLevel=='WARNING') {
        $color='background-color:#FFDDAA80;';
      } else if ($alertLevel=='CRITICAL') {
        $color='background-color:#FF555580;';
      }
      echo '<tr class="tranparent" style="border-top:5px solid transparent;height:30px" '.$goto.' id="displayWork_'.$cptDisplayId.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').' " onmouseover="document.activeElement.blur();">';
//       if (!$print and $alertLevel!='NONE') {
//         echo '<div dojoType="dijit.Tooltip" connectId="displayWork_'.$cptDisplayId.'" position="below" style="z-index:99999">';
//         echo $alertLevelArray['description'];
//         echo '</div>';
//       }
      if (!$print and $alertLevel!='NONE') {
        echo '<td style="position:relative;z-index:99999;min-width:25px;color:#505050" class="tranparent" onMouseEnter="showToolTip(\'todayIndicatorToolTip_'.$cptDisplayId.'\');" onMouseLeave="hideToolTip(\'todayIndicatorToolTip_'.$cptDisplayId.'\', 200);">';
        echo '<img style="width:16px; position:relative;top:2px;" src="../view/css/images/indicator'.pq_ucfirst(pq_strtolower($alertLevel)).'32.png" />';
        echo '<div id="todayIndicatorToolTip_'.$cptDisplayId.'" name="todayIndicatorToolTip_'.$cptDisplayId.'" class="comboButtonInvisible" dojoType="dijit.form.DropDownButton" style="position:absolute;top:20px;left:-6px;width:0px;height:0px;overflow:hidden;">';
        echo '<div dojoType="dijit.TooltipDialog" onMouseEnter="clearTimeout(hideToolTipTimeout);" onMouseLeave="hideToolTip(\'todayIndicatorToolTip_'.$cptDisplayId.'\', 200);">';
        echo '<div>'.$alertLevelArray['description'].'</div>';
        echo '</div>';
        echo '</div>';
        echo '</td>';
      } else {
        echo '<td></td>';
      }
      $type="";
      if(property_exists($elt, 'id'.$class.'Type')){
        $type = SqlList::getNameFromId($class.'Type', $elt->$idType);
      }
      echo '  <td class="messageData tranparent classLinkName" style="vertical-align:middle;width:5%;border:none;'.$color.'">'.formatIcon($class, 22, i18n($class)).'</td>';
      echo '  <td class="messageData tranparent classLinkName" style="vertical-align:middle;width:15%;border:none;'.$color.'">'.htmlEncode(SqlList::getNameFromId('Project', $elt->idProject)).'</td>';
      echo '  <td class="messageData tranparent classLinkName" style="vertical-align:middle;width:10%;border:none;'.$color.'">'.$type.'</td>';
      echo '  <td class="messageData tranparent classLinkName" style="vertical-align:middle;width:40%;border:none;'.$color.'">'.htmlEncode($elt->name).'</td>';
      echo '  <td class="messageDataValue tranparent classLinkName" style="vertical-align:middle;width:15%;min-width:100px;border:none;'.$color.'" NOWRAP>'.htmlFormatDate($echeance).'</td>';
      echo '  <td class="messageData colorNameData" style="vertical-align:middle;width:15%;min-width:100px;border:none;'.$color.'"><div style="height:20px; border-radius:10px; overflow:hidden">'.$displayColorStatus.'</div></td>';
      echo '</tr>';
    }
    if($showAllToday=='true'){
      echo '<tr style="text-align: center;font-weight:bold;"><td colspan="9"  class="messageData"><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconReduceDisplay16" onclick="refreshTodayList(\''.$showAllLib.'\',\'false\')" title="'.i18n('reduceDisplayToday').'">&nbsp;</div></td></tr>';
    }
    echo "</table>";
    echo "</form>";
  }
}

function showSubTask(){
  global $cptMax,$collapsedList,$print;
  echo '<div onMouseOver="dojo.byId(\'hideTodoListDiv\').style.display=\'block\';" onMouseOut="dojo.byId(\'hideTodoListDiv\').style.display=\'none\';">';
  echo '  <table style="width:100%"><tr>';
  echo '   <td class="simple-grid__header">'.i18n('TodoList').'</td>';
  echo '   <td><div  title="'.i18n('hideDivToday').'" id="hideTodoListDiv" style="opacity:40%;display:none;width:24px;position:relative;float:right;">';
  $image='../view/css/images/tabClose.svg';
  echo '<img class="roundedButtonSmall  iconSize22" src="'.$image.'" onClick="hideDivToday(\'hideTodoList\');setTodayParameterHideSection(\'ResponsibleTodoList\');" />';
  echo '</div></td>';
  echo '  </tr>';
  echo '  </table><table style="width:100%">';
  echo '  <tr>&nbsp;</tr>';
  echo '  <tr>';
  echo '  <td></td>';
  echo '  </tr>';
  echo '  </table>';
  echo '</div>';
  $result='';
  $titlePane="Today_TodoList";
  //if (!getSessionUser()->isResource) return;
  $user=getSessionUser();
  $todoList= new SubTask();
  $where="(idResource=".Sql::fmtId($user->id).") and idle=0 and done=0";
  $lstTodoList=$todoList->getSqlElementsFromCriteria(null,null,$where,'idProject ASC, refType ASC, refId ASC, handled ASC, paused ASC');

  $result.= '<form id="todayTodoListForm" name="todayTodoListForm">';
  $result.= '<div style="max-height:245px;overflow-x:hidden;overflow-y:auto">';
  $result.= '<table class="transparent" align="center" style="width:100%">';
  $cpProject=0;
  $cpAct=0;
  if(count($lstTodoList)>0){
    $oldProj='';
    $cpProject=1;
    $cpAct=1;
    $oldRefId = '';
    $oldRefType = '';
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

//         $result.=   '<td class="messageDataValue" rowspan="rowspanProj"  style="'.$styleProj.'" '.$gotoProj.'>'
//         //                       .'<div style="'.$styleDivProj.'margin-left:3%;" class="'.$classDivProj.'">' .formatIcon($projClass, 16, i18n($projClass)).'</div>'
//         .'<div style="text-align:left;'.$styleDivProj.'" class="'.$classDivProj.'" >&nbsp;'.$projectName.'</div>'
//             .'</td>';
      }else{
        $cpProject++;
      }
      $todoStyle='';
      if($oldRefId!=$refId or $oldRefType!=$refType){
        $result = pq_str_replace('rowspanAct', $cpAct, $result);
        $cpAct=1;
        $gotoRefType='';
        $gotoObject=false;
        $styleRefType='vertical-align:top;padding-top:7px; padding-right:5px; border-top: 0px solid #f0f0f0;';
        $todoStyle='border-top: 0px solid #f0f0f0;';
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


        $result.=   '<td  class="todayData"  rowspan="rowspanAct" style="border:none;'.$styleRefType.'" '.$gotoRefType.'>'
            .'  <table><tr><td>'
            .'    <div style="'.$styleDivObj.'margin-left:3%;" class="'.$classDivObj.'">' .formatIcon($refType, 16, i18n($refType)).'</div>'
            .'  </td><td>'
            .'    <div style="text-align:left;margin-left:5px;'.$styleDivObj.'" class="'.$classDivObj.'" >'.$obj->name.'</div>'
            .'  </td></tr></table>'
            .'  </td>';

      }else {
        $cpAct++;
      }

      $goto='';
      $style=$todoStyle;
      $classDiv='';
      if($gotoObject){
        $goto=$gotoRefType;
        $style.='cursor: pointer;';
        $classDiv='classLinkName';
      }



      $result.=   '<td class="todayData '.$classDiv.'" style="vertical-align:middle;border:0;text-align:left;'.$style.'" '.$goto.'><div><span>'.$todo->name.'</span></div></td>';
      
      
      $extraStyle="width:22px;";
      $extraStyleImg="width:22px; height:22px;";
      $extraStyleColor="margin-left:5px;width:22px; height:22px;border-radius:12px;";
      $styleHealth=($print)?'width:10px;height:10px;margin:1px;padding:0;-moz-border-radius:6px;border-radius:6px;border:1px solid #AAAAAA;':'';
      
      //echo '  <td class="todayData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:50px;'.$extraStyle.'" '.$goto.' >'.'    <div class="colorHealth" style="'.$styleHealth.$extraStyleColor.'background:'.$healthColor.';" title="'.$healthName.'">&nbsp;</div>'.'  </td>';
      
      
      $result.=   '<td class="todayData" style="border:none;cursor:default;'.$todoStyle.'"><div class="colorHealth" style="'.$styleHealth.$extraStyleColor.$backgroundColor.';" title="'.i18n('Status').' : '.$status.'">&nbsp;</div></td>';
      $result.=   '<td class="todayData" style="border:none;cursor:default;'.$todoStyle.'"><div class="colorHealth" style="'.$styleHealth.$extraStyleColor.$backgroundPrio.';" title="'.i18n('Priority').' : '.$priority->name.'">&nbsp;</div></td>';
      $result.= '</tr>';
    }
  }else{
    $result.= '<tr><td colspan="2" class="todayData" style="text-align:center;font-style:italic;color:#A0A0A0">'.i18n('noDataToDisplay').'</td></tr>';
  }
  $result = pq_str_replace('rowspanProj', $cpProject, $result);
  $result = pq_str_replace('rowspanAct', $cpAct, $result);
  $result.= '</table>';
  $result.= '</div>';
  $result.= '</form>';
 // $result.= '</div>';
  echo $result;
}

function showApprovers(){
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
  echo '<div onMouseOver="dojo.byId(\'hideDocument\').style.display=\'block\';" onMouseOut="dojo.byId(\'hideDocument\').style.display=\'none\';">';
  echo '  <table style="width:100%"><tr>';
  echo '   <td class="simple-grid__header">'.i18n('toApprove');
  echo '</td>';
  echo '<td>';
  echo '   <div  title="'.i18n('hideDivToday').'" id="hideDocument" style="opacity:40%;display:none;width:24px;position:relative;float:right;">';
  $image='../view/css/images/tabClose.svg';
  echo '<img class="roundedButtonSmall  iconSize22" src="'.$image.'" onClick="hideDivToday(\'hideDocuments\');setTodayParameterHideSection(\'Documents\');" />';
  echo '</div>';
  echo '</td>';
  echo '  </tr>';
  echo '  </table><table style="width:100%">';
  echo '  <tr>&nbsp;</tr>';
  echo '  <tr>';
  echo '  <td></td>';
  echo '  </tr>';
  echo '  </table>';
  echo '</div>';
  $user=getSessionUser();
  if (!$print) {
    echo '<input id="showAll'.$showAllLib.'Today" name="showAll'.$showAllLib.'Today"  hidden value="'.$showAllToday.'" />';
    echo '<form id="today'.$showAllLib.'Form" name="today'.$showAllLib.'Form">';
    echo '<div style="height:234px; overflow-x:hidden;overflow-y:visible;">';
    echo '<table class="transparent" align="left" style="width:100%;text-align:left">';
    $cpt=0;
    $approver = new Approver();
    $lstApprover = $approver->getSqlElementsFromCriteria(null, null, "approved=0 and disapproved=0 and idAffectable=$user->id and idle=0 and refType!='Document'");
    //if (!getSessionUser()->isResource) $lstApprover=array();;
    foreach ($lstApprover as $app){
      if ($app->refType=='Document'){
        continue;
      }
      $extraName="";
      if($app->refType=='DocumentVersion'){
        //continue;
        $docVers=new DocumentVersion($app->refId);
        if (!$docVers->id) continue; // Approver referencing deleted DocumentVersion
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
        echo '<tr><td colspan="2" class="todayData" style="text-align:center;"><div><b>'.i18n('limitedDisplay', array($cptMax)).'</b></div><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconDisplayMore16" onclick="refreshTodayList(\''.$showAllLib.'\',\'true\')" title="'.i18n('displayMore').'" >&nbsp;</div></td></tr>';
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
      $color="background-color:transparent";
      if ($alertLevel=='ALERT') {
        $color='background-color:#FFAAAA80;';
      } else if ($alertLevel=='WARNING') {
        $color='background-color:#FFDDAA80;';
      } else if ($alertLevel=='CRITICAL') {
        $color='background-color:#FF555580;';
      }
      echo '<tr  '.$goto.' id="displayWork_'.$cptDisplayId.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'">';
      if (!$print and $alertLevel!='NONE') {
        echo '<div dojoType="dijit.Tooltip" connectId="displayWork_'.$cptDisplayId.'" position="below">';
        echo $alertLevelArray['description'];
        echo '</div>';
      }


      if(property_exists($elt, $idType)){
        $type = SqlList::getNameFromId($class.'Type', $elt->$idType);
      }
      $nameProject=(property_exists($elt, 'idProject'))?htmlEncode(SqlList::getNameFromId('Project', $elt->idProject)):'';
      echo '  <td class="todayData" style="vertical-align:top;position:relative;top:2px;text-align: left;border:none;'.$color.'">'.formatIcon($class, 16, i18n($class)).'</td>';
      echo '  <td class="todayData" style="margin:0;text-align: left;padding-bottom:10px;padding-right:8px;border:none;'.$color.'">'.htmlEncode($elt->name.$extraName).'</td>';
      echo '</tr>';
      if($showAllToday=='true'){
        echo '<tr style="text-align: center;font-weight:bold;"><td colspan="9" class="messageData"><div style="cursor:pointer;width:16px;height:16px;margin-left:50%;" class="iconReduceDisplay16" onclick="refreshTodayList(\''.$showAllLib.'\',\'false\')" title="'.i18n('reduceDisplayToday').'">&nbsp;</div></td></tr>';
      }
    }
    if ($cpt==0) {
      echo '<tr><td colspan="2" class="todayData" style="text-align:center;font-style:italic;color:#A0A0A0">'.i18n('noDataToDisplay').'</td></tr>';
    }
    echo "</table>";
    echo "</div>";
    echo "</form>";
  }
  echo $result;
}

function showReport($idReport){
  global $print;
  $reportDivClass = (Parameter::getUserParameter('todayReportDivClass'.$idReport) != '')?Parameter::getUserParameter('todayReportDivClass'.$idReport):'simple-grid__cell--1-1';
  $rpt = new Report($idReport);
  $user = getSessionUser();
  $crit=array('idUser'=>$user->id, 'idle'=>'0','idReport'=>$idReport);
  $todayR = Today::getSingleSqlElementFromCriteria('Today', $crit);
  $titlePane="Today_report_".$todayR->id;
  if (!$print) {
    $CategoryName = SqlList::getNameFromId('ReportCategory', $rpt->idReportCategory, false);
    $reportName = ($CategoryName != 'reportCategoryObjectList')?i18n($rpt->name):$rpt->name;
    echo '<div style="height:20px;" class="simple-grid__header"';
    echo ' onMouseOver="showTodayReportButton('.$todayR->id.', true);" onMouseOut="showTodayReportButton('.$todayR->id.', false);" > ';
    echo pq_ucfirst(i18n('colReport')).' &quot;'.$reportName.'&quot;';
    echo '<div  title="'.i18n('hideDivToday').'" id="hideReport'.$todayR->id.'" style="opacity:40%;width:24px;height:17px;float:right;display:none;">';
    $image='../view/css/images/tabClose.svg';
    echo '<img class="roundedButtonSmall  iconSize22" src="'.$image.'" onClick="hideDivToday(\'Report_'.$idReport.'\');setTodayParameterHiderReportSection('.$todayR->id.');" />';
    echo "</div>";
    echo '<div id="extendReport'.$todayR->id.'" style="margin-right:10px;opacity:40%;width:24px;height:17px;float:right;display:none;">';
    $image=($reportDivClass == 'simple-grid__cell--1-2-fix')?'../view/css/customIcons/new/iconExtend.svg':'../view/css/customIcons/new/iconFold.svg';
    echo '<img title="'.i18n('foldSection').'" class="roundedButtonSmall imageColorNewGui iconSize22" src="'.$image.'" onClick="extendReportDivToday('.$idReport.', this);" />';
    echo "</div>";
    echo '<div  title="'.i18n('deleteReportToday').'" id="deleteReport'.$todayR->id.'" style="margin-right:10px;opacity:40%;width:24px;height:17px;float:right;display:none;">';
    $image='../view/css/customIcons/new/iconRemove.svg';
    echo '<img class="roundedButtonSmall imageColorNewGui iconSize22" src="'.$image.'" onClick="hideDivToday(\'Report_'.$idReport.'\');setTodayParameterDeleteReport('.$todayR->id.');" />';
    echo "</div>";
    echo "</div>";
    echo '<div  dojoType="dijit.TitlePane" style="overflow-x:auto;border:0"';
    echo ' open="true"';
    echo ' id="'.$titlePane.'"';
    echo ' title="'.i18n('reportShow').'" >';
    echo ' <script type="dojo/connect" event="onHide" args="evt">';
    echo '   this.set("title","'.i18n('reportShow').'");';
    echo ' saveCollapsed("'.$titlePane.'");';
    echo ' setTimeout(\'dijit.byId("'.$titlePane.'").set("content","");\',100);';
    echo ' </script>';
    echo ' <script type="dojo/connect" event="onShow" args="evt">';
    echo '   this.set("title","'.i18n('reportHide').'");';
    echo '   saveExpanded("'.$titlePane.'");';
    $params=TodayParameter::returnReportParameters($rpt);
    $paramsToday=TodayParameter::returnTodayReportParameters($todayR);
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
    $paramsToday=TodayParameter::returnTodayReportParameters($todayR);
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
?>
