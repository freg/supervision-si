<?php
use function Composer\Autoload\includeFile;
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

  require_once "../tool/projeqtor.php";
  require_once "../tool/formatter.php";
  scriptLog('   ->/view/SubscriptionView.php');
  
  
  // PBER Workaround as at that level projeqtor.php file contains correct $version definition, but $version not actualized yet 
  $mainPQ=file_get_contents("../tool/projeqtor.php");
  $start=pq_strpos($mainPQ,'$version');
  $end=pq_strpos($mainPQ,';',$start);
  $line=pq_substr($mainPQ,$start,$end-$start);
  $version=pq_str_replace(array('$version','=',' ','"',';'), '', $line);

  $needCacheRefresh = RequestHandler::getBoolean('needCacheRefresh');
  if($needCacheRefresh){
    $user=new User();
    $userList=$user->getSqlElementsFromCriteria(null);
    foreach ($userList as $user) {
      $user->_arrayRevisionUpdate = array();
    }
    $user=getSessionUser();
    $user->_arrayRevisionUpdate = array();
  }
  $user=getSessionUser();
  global $canAccesRemoteServer;
  $canAccesRemoteServer=true;
  
  // Get available revision from projeqtor server //
  if(isset($user->_arrayRevisionUpdate) and count($user->_arrayRevisionUpdate) > 0){
    $newRevisionUpdate = $user->_arrayRevisionUpdate;
  }else{
    $jsonRevisionUpdate=RevisionUpdate::getRemoteFile("https://subscription.projeqtor.org/getRevisionUpdates.php");
    $newRevisionUpdate=json_decode($jsonRevisionUpdate,true);
    if (! is_array($newRevisionUpdate)) {
      $newRevisionUpdate=array();
    } 
    if(count($newRevisionUpdate) > 0){
      ksort($newRevisionUpdate);
      $user->_arrayRevisionUpdate = $newRevisionUpdate;
    }
  }
  // End get available revision from projeqtor server //
  
  // Get current revision from database //
  $currentRevisionUpdate=array();
  $revisionUpdate = new RevisionUpdate();
  $currentRevisionUpdateList = $revisionUpdate->getSqlElementsFromCriteria(array('version'=>Sql::getDbVersion()));
  foreach ($currentRevisionUpdateList as $revisionUpdate){
    $currentRevisionUpdate["$revisionUpdate->revisionId"]=array("version"=>"$revisionUpdate->version", "date"=>"$revisionUpdate->date","files"=>array(),"tickets"=>array());
    $jonFiles = json_decode($revisionUpdate->files);
    $files = $jonFiles->files;
    if(is_array($files)){
      foreach ($files as $key=>$file){
        array_push($currentRevisionUpdate["$revisionUpdate->revisionId"]["files"], array("name"=>$file->name, "path"=>$file->path));
      }
    }else{
      $currentRevisionUpdate["$revisionUpdate->revisionId"]["files"] = array("name"=>$files->name, "path"=>$files->path);
    }
    $jonTickets = json_decode($revisionUpdate->tickets);
    $tickets = $jonTickets->tickets;
    if(is_array($tickets)){
      foreach ($tickets as $ticket){
        array_push($currentRevisionUpdate["$revisionUpdate->revisionId"]["tickets"], array("id"=>$ticket->id, "name"=>$ticket->name, "url"=>$ticket->url));
      }
    }else{
      $currentRevisionUpdate["$revisionUpdate->revisionId"]["tickets"] = array("id"=>$tickets->id, "name"=>$tickets->name, "url"=>$tickets->url);
    }
  } 
  // End get current revision from database for subscription //
  
  // Get description for subscription //
  $idPlugin='200300';// id for Install auto plugin
  $urlPlugins = "https://projeqtor.org/admin/getPlugins.php";
  $getYesNo=Parameter::getGlobalParameter('getVersion');
  $json=null;
  if (serverCanAccessRemoteServer()) {
    enableCatchErrors();
    enableSilentErrors();
    //$ctx=stream_context_create(array('http'=>array('timeout' => 5)));
    $ctx=getStreamContext(10);
    $json = file_get_contents($urlPlugins,false,$ctx);
    disableCatchErrors();
    disableSilentErrors();
  }
  $pluginName='';
  $shortDec='';
  $longDesc='';
  $page='';
  $imgLst='';
  $firstImg=null;
  $versionPlg='';
  $userManual='';
  $urlSite='https://www.projeqtor.net/';
  if ($json) {    
    $object = json_decode($json);
    $plugins=$object->items;
    foreach ($plugins as $val){
      if($val->id==$idPlugin){
        $obj=$val;
        break;
      }
    }
  
    $userLang = getSessionValue('currentLocale');
    $lang = "en";
    if(pq_substr($userLang,0,2)=="fr")$lang="fr";
    $pluginName=($lang=='fr')?$obj->nameFr:$obj->nameEn;
    $shortDec=($lang=='fr')?$obj->shortDescFr:$obj->shortDescEn;
    $longDesc=($lang=='fr')?$obj->longDescFr:$obj->longDescEn;
    $page=($lang=='fr')?$obj->pageFr:$obj->pageEn;
    $imgLst=$obj->images;
    $firstImg=$obj->images[0];
    $urlSite='https://www.projeqtor.net/';
    $versionPlg=$obj->version;
    unset($imgLst[0]);
    $userManual=$obj->userManual;
    // End of get description for subscription //
  } else {
    $canAccesRemoteServer=false;
// PBER #10678
//     echo "Cannot access remote information for subscription at ".$urlPlugins;
//     if ($getYesNo=='NO') echo "<br/>Global Parameter 'check for new version' is disabled, so we won't access remote server.";
//     else echo "<br/>Possibly your server has no acces to internet.";
//     exit;
  }
  $lastTab = Parameter::getUserParameter('subscriptionTab');
  if(!pq_trim($lastTab)){
    $lastTab = 'subscriptionDetailTab';
  }
  
  $versionUpdateChannel = Parameter::getGlobalParameter('versionUpdateChannel');
  if(!pq_trim($versionUpdateChannel)){
    $versionUpdateChannel = 'stable';
  }
  $revisionUpdateType = Parameter::getGlobalParameter('revisionUpdateType');
  if(!pq_trim($revisionUpdateType)){
    $revisionUpdateType = 'manual';
  }
  $versionUpdateType = Parameter::getGlobalParameter('versionUpdateType');
  if(!pq_trim($versionUpdateType)){
    $versionUpdateType = 'manual';
  }
  
  $subscriptionCodeStatus = Parameter::getGlobalParameter('subscriptionCodeStatus');
  if(!$subscriptionCodeStatus)$subscriptionCodeStatus='KO';
  $subscriptionCode = Parameter::getGlobalParameter('subscriptionCode');
  $revision=Parameter::getGlobalParameter('lastRevisionInstalled');
  
  $collapsedList=Collapsed::getCollaspedList();
  $isIE=false;
  if (pq_array_key_exists('isIE',$_REQUEST)) {
    $isIE=$_REQUEST['isIE'];
  }
  $dbVersion=Parameter::getGlobalParameter('dbVersion');
  if ($version==$dbVersion) RevisionUpdate::deletePatchFile();
?>  

<input type="hidden" name="objectClassManual" id="objectClassManual" value="Plugin" />

<div dojoType="dijit.layout.BorderContainer" >
  <div dojoType="dijit.layout.ContentPane" region="top" id="subscriptionHeaderDiv" style="width:50%;overflow: hidden;padding-bottom:20px;">
    <script type="dojo/connect" event="onShow" args="evt"><?php Parameter::setDisplaySM();?></script>
    <table width="100%" class="listTitle subscription projeqtorReference">
    <tr>
      <!-- ICON AND NAME -->
      <td style="width:50px;min-width:43px;" align="center">
         <div style="position:absolute;left:0px;width:43px;top:0px;height:36px;" class="iconHighlight">&nbsp;</div>
         <div style="position:absolute; top:3px;left:5px ;" class="iconSubscription32 iconSubscription iconSize32 imageColorNewGui" /></div>
      </td>
      <td class="title" style="height:35px;width:100%;">    
        <div style="width:100%;height:100%;position:relative;">
          <div id="menuName" style="float:left;width:100%;position:absolute;top:8px;text-overflow:ellipsis;overflow:hidden;">
            <span id="classNameSpan" style="">
            <?php echo i18n("menuSubscription");?>
            </span>
          </div>
        </div>
      </td>
    </tr>
    </table>
    <?php if ($version!=$dbVersion) {?>
      <script type="dojo/connect" event="onShow" args="evt">
        showWait();
        noDisconnect=true;
        quitConfirmed=true;        
        dojo.byId("directAccessPage").value="SubscriptionView.php";
        dojo.byId("menuActualStatus").value=menuActualStatus;
        dojo.byId("p1name").value=null;
        dojo.byId("p1value").value=null;
        dojo.byId("directAccessForm").submit();      
	    </script>';
    <?php } else if (getSessionValue('installRevision')=='true') {
      unsetSessionValue('installRevision');?>
      <script type="dojo/connect" event="onShow" args="evt">
        //adminCronRestart(); // PBER : do not restart cron that is not running  
	    </script>';
	  <?php }?>
  </div>
  <div id="subscriptionCenterDiv" class="listTitle" dojoType="dijit.layout.ContentPane" region="center">
    <div id="subscriptionTabContainer" data-dojo-type="dijit.layout.TabContainer" style="width: 100%;padding-left:32px;" doLayout="true">
      <?php if (serverCanAccessRemoteServer()) {?>
      <div id="subscriptionDescriptionTab" title="<?php echo i18n('tabDescription');?>" class="transparentBackground" data-dojo-type="dijit.layout.ContentPane" style="overflow: hidden;" data-dojo-props="<?php echo (($lastTab == 'subscriptionDescriptionTab')?'selected:true':''); ?>">
        <script type="dojo/connect" event="onShow" args="evt">
              dijit.byId('subscriptionTabContainer').watch("selectedChildWidget", function(name, oldValue, newValue) {
                saveDataToSession('subscriptionTab', newValue.id,true);
              });
        </script>
        <div dojoType="dijit.layout.ContentPane" region="center" style="overflow-y:auto;">
        <div class="container" dojoType="dijit.layout.BorderContainer">
          <div id="subscriptionShopDiv" class="listTitle" dojoType="dijit.layout.ContentPane" region="top" style="z-index:3;overflow:visible">
            <table style='width:100%;' >
              <tr>
                <td style="vertical-align: top;width:300px!important;">
                  <div style="vertical-align: middle;float:left;width:300px;text-align:center;margin-top:25px;">
                    <span  class="title" style="font-size:20px;white-space: unset;"><?php echo $pluginName;?>&nbsp;</span>
                    
                  </div>
                  <img style="position:absolute;top:10px;left:-10px;border:none !important;float:left;width:50px;height:50px;margin-left:25px;margin-right:25px;"  src="<?php echo $urlSite.$firstImg->url;?>"></img>
                </td>
                <td style="vertical-align:bottom;" ></td>
              </tr>
            </table>
            <div style="margin-top:45px;margin-left:35px;margin-bottom:25px;">
              <div class="roundedVisibleButton roundedButton generalColClass pluginShopButton" title="<?php echo('goToThePage'); ?>"  onclick="directionExternalPage('<?php echo $page?>')">
                <div style="position: relative;width:100%;height:100%;"><span style="top:12px;vertical-align:middle;"><?php echo i18n('goToTheServicePage');?></span></div>
              </div>
              <span class="listTitle" style="font-size:14px;font-weight:bold;" ><?php echo $shortDec;?></span>
              <div style="height:20px;">&nbsp;</div>
            </div>
          </div>
          <div dojoType="dijit.layout.ContentPane" region="center" style="height:48px;margin-left:40px;margin-top:25px;" >
            <div class="longDescSubscription" style="padding: 10px;" ><?php echo $longDesc;?></div>
          </div>
        </div>
      </div>
      </div>
      <?php }?>
      <?php if(serverCanAccessRemoteServer() and $subscriptionCodeStatus == 'OK'){?>
      <div id="subscriptionCurrentRevisionTab" title="<?php echo i18n('currentRevision');?>" class="transparentBackground" data-dojo-type="dijit.layout.ContentPane" style="overflow: hidden;" data-dojo-props="<?php echo (($lastTab == 'subscriptionCurrentRevisionTab')?'selected:true':''); ?>">
        <script type="dojo/connect" event="onShow" args="evt">
              dijit.byId('subscriptionTabContainer').watch("selectedChildWidget", function(name, oldValue, newValue) {
                saveDataToSession('subscriptionTab', newValue.id,true);
                updateRevisionSelectedLine(null, null, null, 'current');
                clearAllFilterRevisionList('current');
              });
        </script>
        <div class="subscriptionBackground" style="padding: 10px;font-weight:bold;">
          <?php echo i18n('actualVersion').' : '.Sql::getDbVersion().' | '.ucfirst(i18n('colRevision')).' : '.$revision; ?>
        </div>
        <div id="currentRevisionUpdateTableDiv" name="currentRevisionUpdateTableDiv" dojoType="dijit.layout.ContentPane" region="center">
          <?php RevisionUpdate::drawRevisionUpdateTable($currentRevisionUpdate, null, 'current');?>
        </div>
      </div>
      <div id="subscriptionAvailableRevisionTab" title="<?php echo i18n('availableRevision');?>" class="transparentBackground" data-dojo-type="dijit.layout.ContentPane" style="overflow: hidden;" data-dojo-props="<?php echo (($lastTab == 'subscriptionAvailableRevisionTab')?'selected:true':''); ?>">
        <script type="dojo/connect" event="onShow" args="evt">
              dijit.byId('subscriptionTabContainer').watch("selectedChildWidget", function(name, oldValue, newValue) {
                saveDataToSession('subscriptionTab', newValue.id,true);
                updateRevisionSelectedLine(null, null, null, 'current');
                clearAllFilterRevisionList('current');
              });
        </script>
        <div style="padding: 10px;font-weight:bold;"><?php echo i18n('actualVersion').' : '.Sql::getDbVersion().' | '.ucfirst(i18n('colRevision')).' : '.$revision; ?></div>
        <div dojoType="dijit.TitlePane" id="revisionRequiermentTitlePane" open="<?php echo ( pq_array_key_exists("revisionRequiermentTitlePane", $collapsedList)?'false':'true');?>"
         onHide="saveCollapsed('revisionRequiermentTitlePane');" onShow="saveExpanded('revisionRequiermentTitlePane');" title="<?php echo i18n('resultUpdated');?>" style="width:98%;">
          <div id="revisionRequirementUpdateTableDiv" name="revisionRequirementUpdateTableDiv" dojoType="dijit.layout.ContentPane" region="center">
            <?php RevisionUpdate::drawRequirementForUpdateTable('revision');?>
          </div>
        </div>
        <div id="newRevisionUpdateTableDiv" name="newRevisionUpdateTableDiv" dojoType="dijit.layout.ContentPane" region="center">
          <?php RevisionUpdate::drawRevisionUpdateTable($newRevisionUpdate, null, 'new');?>
        </div>
      </div>
      <div id="subscriptionAvailableVersionTab" title="<?php echo i18n('availableVersion');?>" class="transparentBackground" data-dojo-type="dijit.layout.ContentPane" style="overflow: hidden;" data-dojo-props="<?php echo (($lastTab == 'subscriptionAvailableVersionTab')?'selected:true':''); ?>">
        <script type="dojo/connect" event="onShow" args="evt">
              dijit.byId('subscriptionTabContainer').watch("selectedChildWidget", function(name, oldValue, newValue) {
                saveDataToSession('subscriptionTab', newValue.id,true);
                updateRevisionSelectedLine(null, null, null, 'current');
                clearAllFilterRevisionList('current');
              });
        </script>
        <div style="padding: 10px;font-weight:bold;"><?php echo i18n('actualVersion').' : '.Sql::getDbVersion().' | '.ucfirst(i18n('colRevision')).' : '.$revision; ?></div>
        <div dojoType="dijit.TitlePane" id="versionRequiermentTitlePane" open="<?php echo ( pq_array_key_exists("versionRequiermentTitlePane", $collapsedList)?'false':'true');?>"
         onHide="saveCollapsed('versionRequiermentTitlePane');" onShow="saveExpanded('versionRequiermentTitlePane');" title="<?php echo i18n('resultUpdated');?>" style="width:98%;">
          <div id="versionRequirementUpdateTableDiv" name="versionRequirementUpdateTableDiv" dojoType="dijit.layout.ContentPane" region="center">
            <?php RevisionUpdate::drawRequirementForUpdateTable('version');?>
          </div>
        </div>
        <div id="versionUpdateTableDiv" name="versionUpdateTableDiv" dojoType="dijit.layout.ContentPane" region="center" style="width:50%;">
          <table style="width:100%;">
            <tr>
              <td style="width:5%" >&nbsp;</td>
              <td class="display" >
               <?php echo i18n('installAutoList');?>
              <br/><br/></td>
            </tr>
          </table>
          <table style="width:100%;">
            <?php RevisionUpdate::displayInstallationList('local');?>
          </table><br/>
          <table style="width:100%;">
            <tr height="30px"> 
              <td class="dialogLabel" style="width:320px";>
                <label for="uploadPlugin" style="width:320px"><?php echo i18n("installAutoAdd");?>&nbsp;:&nbsp;</label>
              </td>
              <td style="text-align:left;">
               <input type="hidden" name="MAX_FILE_SIZE" value="<?php echo Parameter::getGlobalParameter('paramAttachmentMaxSize');?>" />     
               <?php  if ($isIE and $isIE<=9) {?>
               <input MAX_FILE_SIZE="<?php echo Parameter::getGlobalParameter('paramAttachmentMaxSize');?>"
                dojoType="dojox.form.FileInput" type="file" class="dynamicTextButton"
                name="installAutoFile" id="installAutoFile" 
                cancelText="<?php echo i18n("buttonReset");?>"
                label="<?php echo i18n("buttonBrowse");?>"
                title="<?php echo i18n("helpSelectFile");?>" />
               <?php } else {?>  
               <div MAX_FILE_SIZE="<?php echo Parameter::getGlobalParameter('paramAttachmentMaxSize');?>"
                dojoType="dojox.form.Uploader" type="file"  class="dynamicTextButton pluginFile" 
                url="../plugin/installAuto/installAutoUpload.php"
                target="installAutoPost"
                name="installAutoFile" id="installAutoFile" 
                cancelText="<?php echo i18n("buttonReset");?>"
                multiple="false" 
                uploadOnSelect="true"
                onBegin="installAutoUpload();"
                onChange="installAutoChangeFile(this.getFileList());"
                onError="strt='<?php echo i18n("installAutoErrorUpload");?>';showConfirm(strt.replace(/\\/g,''), function(){});hideWait(); dojo.style(dojo.byId('downloadProgress'), {display:'none'});"
                label="<?php echo i18n("buttonBrowse");?>"
                title="<?php echo i18n("helpSelectFile");?>">
                <script type="dojo/connect" event="onComplete" args="dataArray">
                    installAutoSaveAck(dataArray);
	                </script>
        				<script type="dojo/connect" event="onProgress" args="data">
                    installAutoSaveAttachmentProgress(data);
	                </script>
              </div>
               <?php }?>
               <i><span xname="installAutoFileName" id="installAutoFileName"></span></i> 
                <div style="display:none">
                  <iframe name="installAutoPost" id="installAutoPost" jsid="installAutoPost"></iframe>
                </div>
              </td>
            </tr>
            <tr><td></td><td></tr>
          </table>
          <table style="width:100%;">
            <tr>
              <td>
            <?php 
            $jsonFile=RevisionUpdate::getRemoteFile("https://projeqtor.org/admin/getInstallableVersions.php");
            if ($jsonFile!==false) {
              $jsonList=json_decode($jsonFile,true);
              if(count($jsonList)!=0){
              ?>
              <p style="font-weight:bold;"><?php echo i18n("installAutoOr");?></p> <br/>
              <p><?php echo i18n("installAutoDownloadFrom");?></p> <br/>
              <div id="listVersionAvailable" dojoType="dijit.layout.ContentPane" region="center" style="overflow-y:auto;"> 
                <?php 
                ksort($jsonList);
                if($jsonList){
                  $lastStable=-1;
                  foreach ($jsonList as $key=>$val){
                    if($val['stable']=='Y')$lastStable=$key;
                  }
                  echo '<table><tr>
                  <td class="linkHeader" style="width:50%">'.i18n("colIdVersion").'</td>
                  <td class="linkHeader" style="width:50%">' . i18n('colElement') . '</td></tr>
                  ';
                  foreach ($jsonList as $key=>$val){
                    echo '<tr><td class="linkData" '.($val['stable']=='Y' || $val['last']=='Y' ? 'style="font-weight:bold;cursor:pointer;'.($lastStable==$key ? 'background-color:#AAFFAA;' : '').'" onclick="installationDownloadRemote(\''.$key.'\');"' : '').'>'.$key.($lastStable==$key ? ' '.i18n('installAutoAdvisedVersion'):'').'</td><td class="linkData" style="'.($lastStable==$key ? 'background-color:#AAFFAA;' : '').'">'.($val['last']=='Y' || $lastStable==$key ? i18n('installationLast').' ':'').($val['stable']=='Y' ? i18n('installationStable'):i18n('installationUnstable')).'</td></tr>';
                  }
                  echo '</table>';
                }
              }
              ?>
            </div>
            <?php
            } else {
              echo i18n("installAutoConfigureProxy");
            ?>
              <form id="proxyForm" jsId="proxyForm" name="proxyForm" encType="multipart/form-data" action="" method="">
              <label class="label"><?php echo i18n('installAutoProxyHost');?> : </label><input type="text" dojoType="dijit.form.TextBox" id="installAutoProxyHost" name="installAutoProxyHost" class="input" style="width:250px" value="<?php echo Parameter::getGlobalParameter('paramProxy');?>"/>&nbsp;(<?php echo i18n('installAutoProxyHostHelp');?>)<br/>
              <label class="label"><?php echo i18n('installAutoProxyUser');?> : </label><input type="text" dojoType="dijit.form.TextBox" id="installAutoProxyUser" name="installAutoProxyUser" class="input" style="width:250px" value="<?php echo Parameter::getGlobalParameter('paramProxyUser');?>"/>&nbsp;(<?php echo i18n('installAutoProxyUserHelp');?>)<br/>
              <label class="label"><?php echo i18n('installAutoProxyPass');?> : </label><input type="password" dojoType="dijit.form.TextBox" id="installAutoProxyPass" name="installAutoProxyPass" class="input" style="width:250px" value="<?php echo Parameter::getGlobalParameter('paramProxyPassword');?>"/><br/>
              <label class="label"></label><button id="installAutoProxySave" dojoType="dijit.form.Button" showlabel="true"
                  title="<?php echo i18n('showDetail')?>" >
                  <?php echo "OK";?>
                  <script type="dojo/connect" event="onClick" args="evt">
                    installAutoSaveProxy();
                  </script>
              </button>
              </form>
            <?php
            }
            ?>
            <div id="containerDownloader" dojoType="dijit.layout.ContentPane" style="margin-top:40px;" region="center">
              
            </div>
              </td>
            </tr>
          </table>
        </div>
      </div>
      <?php }?>
      <div id="subscriptionConfigurationTab" title="<?php echo i18n('tabConfiguration');?>" class="transparentBackground" data-dojo-type="dijit.layout.ContentPane" style="overflow: hidden;" data-dojo-props="<?php echo (($lastTab == 'subscriptionConfigurationTab')?'selected:true':''); ?>">
        <script type="dojo/connect" event="onShow" args="evt">
              dijit.byId('subscriptionTabContainer').watch("selectedChildWidget", function(name, oldValue, newValue) {
                saveDataToSession('subscriptionTab', newValue.id,true);
                clearAllFilter();
              });
        </script>
        <div style="padding: 10px">
          <form dojoType="dijit.form.Form" id="subscriptionConfigurationForm" name="subscriptionConfigurationForm" onSubmit="return false;" >
            <input type="hidden" name="msgClosedApplication" id="msgClosedApplication" value="<?php echo Parameter::getGlobalParameter('msgClosedApplication'); ?>"/>
            <table style="width:98%;">
              <tr>
                <td colspan="2" style="padding-bottom:10px;font-weight:bold;"><?php echo i18n('actualVersion').' : '.Sql::getDbVersion().' | '.ucfirst(i18n('colRevision')).' : '.$revision; ?></td>
              </tr>
              <?php if (!serverCanAccessRemoteServer()) {?>
              <tr><td></td><td style=""><?php echo serverCanAccessRemoteServerReason();?></td></tr>
              <?php }?>
              <tr>
                <td class="label" style="width:225px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo i18n("colUniqueCode"). Tool::getDoublePoint();?>
                </td>
                 <td class="display" style="padding-top:10px; padding-bottom:10px"><?php echo System::getUniqueCode();?>
                 </td>
              </tr>
              <tr>
                <td class="label" style="width:225px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo i18n("subscriptionCode"). Tool::getDoublePoint();?>
                </td>
                <td class="display">
                  <input dojoType="dijit.form.TextBox" id="subscribeCodeInput" name="subscribeCodeInput" class="input" style="width:200px;" placeholder="<?php echo i18n('subscriptionCodePlaceholder');?>" value="<?php echo $subscriptionCode;?>"/>
                  <button id="checkSubscribeCode" dojoType="dijit.form.Button" showlabel="true"' 
                    class="dynamicTextButton" title="<?php echo i18n('checkSubscribeCodeButton');?>" >
                    <span><?php echo i18n('checkSubscribeCodeButton');?></span>
                    <script type="dojo/connect" event="onClick" args="evt">
                        checkSubscribeCode('manual');
                      </script>
                  </button>
                </td>
              </tr>
            </table>
            <?php if(serverCanAccessRemoteServer() and $subscriptionCodeStatus == 'OK'){?>
            <div dojoType="dijit.TitlePane" id="revisionTitlePane" open="<?php echo ( pq_array_key_exists("revisionTitlePane", $collapsedList)?'false':'true');?>"
             onHide="saveCollapsed('revisionTitlePane');" onShow="saveExpanded('revisionTitlePane');" title="<?php echo i18n('colRevision');?>" style="width:98%;">
              <table>
                <tr>
                  <td class="label" style="width:225px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                    <?php echo i18n("updateType"). Tool::getDoublePoint();?>
                  </td>
                  <td class="display">
                    <select dojoType="dijit.form.FilteringSelect" class="input" style="width:200px;" <?php echo autoOpenFilteringSelect();?> name="revisionUpdateType" id="revisionUpdateType" value="<?php echo $revisionUpdateType;?>">
                        <option value="manual"><?php echo i18n('manual')?></option>
                        <option value="automatique"><?php echo i18n('automatique')?></option>
                         <script type="dojo/connect" event="onChange" args="evt">
                          saveGlobaleParameter('revisionUpdateType', this.value);
                          refreshFrequencyUpdateTable('revision', this.value);
                          if (this.value == 'manual') cronActivation('SubscriptionUpdateRevision',false,true);
                       </script>
                    </select>
                  </td>
                </tr>
                <tr>
                  <td colspan="2">
                  <?php $displayRevisionFrequencyUpdate = ($revisionUpdateType == 'manual')?'display:none':'';?>
                    <div id="revisionFrequencyUpdateTableDiv" name="revisionFrequencyUpdateTableDiv" dojoType="dijit.layout.ContentPane" region="center" style="<?php echo $displayRevisionFrequencyUpdate; ?>">
                      <?php RevisionUpdate::drawUpdateTypeTable('revision'); ?>
                    </div>
                  </td>
                </tr>
              </table>
            </div>
            <div dojoType="dijit.TitlePane" id="versionTitlePane" open="<?php echo ( pq_array_key_exists("versionTitlePane", $collapsedList)?'false':'true');?>"
             onHide="saveCollapsed('versionTitlePane');" onShow="saveExpanded('versionTitlePane');" title="<?php echo i18n('colVersion');?>" style="width:98%;">
             <table>
                <tr>
                  <td class="label" style="width:225px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                    <?php echo i18n("versionChannel"). Tool::getDoublePoint();?>
                  </td>
                  <td class="display">
                    <select dojoType="dijit.form.FilteringSelect" class="input" style="width:200px;" <?php echo autoOpenFilteringSelect();?> name="versionUpdateChannel" id="versionUpdateChannel" value="<?php echo $versionUpdateChannel;?>">
                        <option value="stable"><?php echo i18n('channelStable')?></option>
                        <option value="unstable"><?php echo i18n('channelRelease')?></option>
                         <script type="dojo/connect" event="onChange" args="evt">
                          saveGlobaleParameter('versionUpdateChannel', this.value);
                          refreshFrequencyUpdateTable('version', this.value);
                       </script>
                    </select>
                  </td>
                </tr>
                <tr>
                  <td class="label" style="width:225px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                    <?php echo i18n("updateType"). Tool::getDoublePoint();?>
                  </td>
                  <td class="display">
                    <select dojoType="dijit.form.FilteringSelect" class="input" style="width:200px;" <?php echo autoOpenFilteringSelect();?> name="versionUpdateType" id="versionUpdateType" value="<?php echo $versionUpdateType;?>">
                        <option value="manual"><?php echo i18n('manual')?></option>
                        <option value="automatique"><?php echo i18n('automatique')?></option>
                         <script type="dojo/connect" event="onChange" args="evt">
                          saveGlobaleParameter('versionUpdateType', this.value);
                          refreshFrequencyUpdateTable('version', this.value);
                          if (this.value == 'manual') cronActivation('SubscriptionUpdateVersion',false,true);
                       </script>
                    </select>
                  </td>
                </tr>
                <tr>
                  <td colspan="2">
                    <?php $displayVersionFrequencyUpdate = ($versionUpdateType == 'manual')?'display:none':'';?>
                    <div id="versionFrequencyUpdateTableDiv" name="versionFrequencyUpdateTableDiv" dojoType="dijit.layout.ContentPane" region="center" style="<?php echo $displayVersionFrequencyUpdate;?>">
                      <?php RevisionUpdate::drawUpdateTypeTable('version'); ?>
                    </div>
                  </td>
                </tr>
              </table>
            </div>
            <?php }?>
          </form>
          <br/>
        </div>
      </div>
    </div>
  </div>
</div>