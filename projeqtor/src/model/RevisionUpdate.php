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

/* ============================================================================
 * Parameter is a global kind of object for parametring.
 * It may be on user level, on project level or on global level.
 */ 
require_once('_securityCheck.php');
class RevisionUpdate extends SqlElement {

  // extends SqlElement, so has $id
  public $id;
  public $revisionId;
  public $version;
  public $date;
  public $files;
  public $tickets;
  
  public $_noHistory=true; // Will never save history for this object
  
  /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

  
  /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }
  
  /**
   * Build the date maps used to filter the revision/ticket/file tables by date.
   * Returns ['ticket' => ['#id' => 'YYYY-MM-DD YYYY-MM-DD ...'], 'file' => [path => '...']].
   * A same ticket or file may belong to several revisions, hence the list of dates.
   */
  public static function buildRevisionDateMaps($arrayRevisionUpdate, $revisionId=null){
    $ticketDates = array();
    $fileDates = array();
    if (!$arrayRevisionUpdate or isset($arrayRevisionUpdate['ERROR'])) {
      return array('ticket'=>array(), 'file'=>array());
    }
    foreach ($arrayRevisionUpdate as $rev=>$upd) {
      if ($revisionId and $rev != $revisionId) continue;
      $d = pq_substr($upd['date'], 0, 10);
      if (!$d) continue;
      if (is_array($upd['tickets'])) {
        foreach ($upd['tickets'] as $t) {
          $id = (isset($t['id']) and $t['id'] != '') ? $t['id'] : '0000';
          if (!isset($ticketDates['#'.$id])) $ticketDates['#'.$id] = array();
          if (!in_array($d, $ticketDates['#'.$id])) $ticketDates['#'.$id][] = $d;
        }
      }
      if (is_array($upd['files'])) {
        foreach ($upd['files'] as $f) {
          $isShortLang = ($f['name'] == "lang.js" and $f['path'] != "tool/i18n/nls/lang.js");
          $path = $isShortLang ? "tool/i18n/nls/*/lang.js" : $f['path'];
          if (!isset($fileDates[$path])) $fileDates[$path] = array();
          if (!in_array($d, $fileDates[$path])) $fileDates[$path][] = $d;
        }
      }
    }
    // Flatten to space-separated strings for direct use as HTML attribute
    foreach ($ticketDates as $k=>$v) $ticketDates[$k] = implode(' ', $v);
    foreach ($fileDates as $k=>$v) $fileDates[$k] = implode(' ', $v);
    return array('ticket'=>$ticketDates, 'file'=>$fileDates);
  }

  public static function drawRevisionUpdateTable($arrayRevisionUpdate, $revisionId, $table){
    if(!isNewGui()){
      $iconViewPosition = "right:4px;top:3px;";
    }else{
      $iconViewPosition = "right:6px;top:10px;";
    }
    
    $langFiles = array();
    if($arrayRevisionUpdate and !isset($arrayRevisionUpdate['ERROR'])){
      foreach ($arrayRevisionUpdate as $revision=>$update){
        if ($revisionId and $revision != $revisionId)continue;
        foreach ($update['files'] as $files){
          if($files['name'] == 'lang.js' and $files['path'] != "tool/i18n/nls/lang.js"){
            if(pq_strpos($files['path'], "tool/i18n/nls/el/") !== false and $files['path'] != "tool/i18n/nls/el/lang.js"){
              $cutFilePath = pq_str_replace("tool/i18n/nls/el/", "", $files['path']);
            }else{
              $cutFilePath = pq_str_replace("tool/i18n/nls/", "", $files['path']);
            }
            $cutFilePath = pq_str_replace("/".$files['name'], "", $cutFilePath);
            if(!in_array($cutFilePath, $langFiles)){
              array_push($langFiles, $cutFilePath);
            }
          }
        }
      }
      $langTitle = i18n('revisionLangTitle')."\n";
      foreach ($langFiles as $lang){
        $langTitle .= "$lang\n";
      }
    }
    $screenHeight=getSessionValue('screenHeight');
    $tabHeight=$screenHeight-(($table=='new')?525:331);
    if (RequestHandler::isCodeSet('destinationHeight')) {
      $targetHeight=intval(RequestHandler::getValue('destinationHeight'));
      if ($targetHeight) {
        $tabHeight=$targetHeight-(($table=='new')?450:256);
      }
    }
    echo '<br/>';
    
    // Build unique date list (YYYY-MM-DD, descending) from the revisions for the date filter
    $revisionDates = array();
    if ($arrayRevisionUpdate and !isset($arrayRevisionUpdate['ERROR'])) {
      foreach ($arrayRevisionUpdate as $__u) {
        $__d = pq_substr($__u['date'], 0, 10);
        if ($__d) { $revisionDates[$__d] = true; }
      }
    }
    $revisionDates = array_keys($revisionDates);
    rsort($revisionDates);

    echo '<table style="">';
    echo '  <tr>';
    echo '    <td style="white-space:nowrap;">';
    echo '      <span style="vertical-align:middle;">'.i18n('colFilterDate'.ucfirst($table)).Tool::getDoublePoint().'</span>';
    echo '      <select dojoType="dijit.form.FilteringSelect" id="'.$table.'RevisionDateFilter" name="'.$table.'RevisionDateFilter"'
              .' class="input" style="width:110px;vertical-align:middle;" '.autoOpenFilteringSelect()
              .' onChange="filterInstalledRevisionByDate(this.value, \''.$table.'\')">';
    echo '        <option value=""></option>';
    foreach ($revisionDates as $__d) {
      echo '        <option value="'.$__d.'">'.htmlFormatDate($__d).'</option>';
    }
    echo '      </select>';
    echo '    </td>';
    echo '    <td colspan="4">';
    if($table=='new'){
    echo '      <div style="position:relative;float:right;top: -10px;" onclick="refreshRevisionUpdateCache()" title="'.i18n('refreshRevisionUpdateCache').'">'.formatBigButton('Refresh').'</div>';
    }
    echo '    </td>';
    echo '  </tr>';
    echo '  <tr style="height:20px">';
    echo '    <td class="section" style="width:100px !important;">'.(($table == 'current')?i18n('titleInstalled'):i18n('titleAvailable')).'</td>';
    echo '    <td class="" style="width:10px !important;">&nbsp;</td>';
    echo '    <td class="section" style="width:400px !important;">'.i18n('menuTicket').'</td>';
    echo '    <td class="" style="width:10px !important;">&nbsp;</td>';
    echo '    <td class="section" style="width:400px !important;">'.i18n('tabFichier').'</td>';
    echo '  </tr>';
    echo '  <tr style="height:20px">';
    echo '    <td style="position:relative">';
    echo '      <input dojoType="dijit.form.TextBox" id="'.$table.'RevisionUpdateAvailablesSearch" class="input" style="" value="" onKeyUp="filterRevisionList(\'Availables\', \''.$table.'\');" />';
    echo '      <div id="'.$table.'IconSearchAvailables" name="'.$table.'IconSearchAvailables"  style="position:absolute;z-index: 99;cursor: pointer;'.$iconViewPosition.'" class="iconSearch iconSize16 imageColorNewGuiNoSelection"></div>';
    echo '      <div id="'.$table.'IconCancelAvailables" name="'.$table.'IconCancelAvailables" style="display:none;position:absolute;z-index: 99;cursor: pointer;'.$iconViewPosition.'" class="iconCancel iconSize16 imageColorNewGuiNoSelection"  onclick="clearFilterRevisionList(\'Availables\', \''.$table.'\');"></div>';
    echo '    </td>';
    echo '    <td>&nbsp;</td>';
    echo '    <td style="position:relative;">';
    echo '      <input dojoType="dijit.form.TextBox" id="'.$table.'RevisionUpdateTicketsSearch" class="input" style="" value="" onKeyUp="filterRevisionList(\'Tickets\', \''.$table.'\');" />';
    echo '      <div id="'.$table.'IconSearchTickets" name="'.$table.'IconSearchTickets" style="position:absolute;z-index: 99;cursor: pointer;'.$iconViewPosition.'" class="iconSearch iconSize16 imageColorNewGuiNoSelection"></div>';
    echo '      <div id="'.$table.'IconCancelTickets" name="'.$table.'IconCancelTickets " style="display:none;position:absolute;z-index: 99;cursor: pointer;'.$iconViewPosition.'" class="iconCancel iconSize16 imageColorNewGuiNoSelection"  onclick="clearFilterRevisionList(\'Tickets\', \''.$table.'\');"></div>';
    echo '    </td>';
    echo '    <td>&nbsp;</td>';
    echo '    <td style="position:relative;">';
    echo '      <input dojoType="dijit.form.TextBox" id="'.$table.'RevisionUpdateFilesSearch" class="input" style="" value="" onKeyUp="filterRevisionList(\'Files\', \''.$table.'\');" />';
    echo '      <div id="'.$table.'IconSearchFiles" name="'.$table.'IconSearchFiles" style="position:absolute;z-index: 99;cursor: pointer;'.$iconViewPosition.'" class="iconSearch iconSize16 imageColorNewGuiNoSelection"></div>';
    echo '      <div id="'.$table.'IconCancelFiles" name="'.$table.'IconCancelFiles " style="display:none;position:absolute;z-index: 99;cursor: pointer;'.$iconViewPosition.'" class="iconCancel iconSize16 imageColorNewGuiNoSelection"  onclick="clearFilterRevisionList(\'Files\', \''.$table.'\');"></div>';
    echo '    </td>';
    echo '  </tr>';
    echo '  <tr>';
    echo '    <td style="position:relative;vertical-align:top;">';
    echo '      <div style="height:100%;max-height:'.$tabHeight.'px;overflow:auto;border: 1px solid #aaaaaa" id="'.$table.'RevisionUpdateAvailables"  name="'.$table.'RevisionUpdateAvailables">';
    if($arrayRevisionUpdate and !isset($arrayRevisionUpdate['ERROR'])){
      $dateMaps = self::buildRevisionDateMaps($arrayRevisionUpdate, $revisionId);
      $ticketDates = $dateMaps['ticket'];
      $fileDates = $dateMaps['file'];
      echo '      <table style="width:100%">';
      foreach ($arrayRevisionUpdate as $revision=>$update){
        $lineClass = ($revisionId and $revision == $revisionId)?'subsUpdateVersionLineSelected':'subsUpdateVersionLine';
        $revDate = pq_substr($update['date'], 0, 10);
        echo '      <tr id="'.$table.'RevisionLine'.$revision.'" data-revdates="'.$revDate.'" class="'.$lineClass.'" onclick="updateRevisionSelectedLine(\''.$revision.'\', null, null, \''.$table.'\')">';
        echo '        <td class="updateSubData '.$table.'Availables" value="'.$revision.' '.$update['version'].'">'.$revision.'</td>';
        echo '        <td class="updateSubData" >'.$update['version'].'</td>';
        echo '        <td class="updateSubData">'.htmlFormatDateTime($update['date'], false).'</td>';
        echo '      </tr>';
      }
      echo '      </table>';
    }
    echo '      </div>';
    echo '    </td>';
    echo '    <td></td>';
    echo '    <td style="position:relative;vertical-align:top;">';
    echo '      <div style="height:100%;max-height:'.$tabHeight.'px;overflow:auto;border: 1px solid #aaaaaa" id="'.$table.'RevisionUpdateTickets" name="'.$table.'RevisionUpdateTickets">';
    if($arrayRevisionUpdate and !isset($arrayRevisionUpdate['ERROR'])){
      echo '      <table style="width:100%">';
      $arrayTickets=array();
      foreach ($arrayRevisionUpdate as $revision=>$update){
        if ($revisionId and $revision != $revisionId)continue;
        if(is_array($update['tickets'])){
          foreach ($update['tickets'] as $tickets){
            $idTicket = (isset($tickets['id']) and $tickets['id'] != '')?$tickets['id']:'0000';
            if(!isset($arrayTickets['#'.$idTicket])){
              $arrayTickets['#'.$idTicket]=$tickets;
              $nameTicket = (isset($tickets['name']))?$tickets['name']:'';
              $lineClass = ($revisionId and $revision == $revisionId)?'subsUpdateVersionLineSelected':'subsUpdateVersionLine';
              $ticketRevDates = isset($ticketDates['#'.$idTicket]) ? $ticketDates['#'.$idTicket] : '';
              echo '      <tr id="'.$table.'TicketLine'.$idTicket.'" data-revdates="'.$ticketRevDates.'" class="'.$lineClass.'" onclick="updateRevisionSelectedLine(null, \''.$idTicket.'\', null, \''.$table.'\')">';
              echo '        <td class="updateSubData '.$table.'Tickets" value="'.$idTicket.' '.$nameTicket.'">#'.$idTicket.'</td>';
              echo '        <td class="updateSubData">'.$nameTicket.'</td>';
              echo '      </tr>';
            }else{
              continue;
            }
          }
        }else{
          echo '      <tr>';
          echo '        <td class="updateSubData '.$table.'Tickets" value=""></td>';
          echo '        <td class="updateSubData"></td>';
          echo '      </tr>';
        }
      }
      echo '      </table>';
    }
    echo '      </div>';
    echo '    </td>';
    echo '    <td></td>';
    echo '    <td style="position:relative;vertical-align:top;">';
    echo '      <div style="height:100%;max-height:'.$tabHeight.'px;overflow:auto;border: 1px solid #aaaaaa" id="'.$table.'RevisionUpdateFiles" name="'.$table.'RevisionUpdateFiles">';
    if($arrayRevisionUpdate and !isset($arrayRevisionUpdate['ERROR'])){
      echo '      <table style="width:100%">';
      $arrayFiles=array();
      foreach ($arrayRevisionUpdate as $revision=>$update){
        if ($revisionId and $revision != $revisionId)continue;
        $lineClass = ($revisionId and $revision == $revisionId)?'subsUpdateVersionLineSelected':'subsUpdateVersionLine';
        foreach ($update['files'] as $files){
          $isShortLang = ($files['name'] == "lang.js" and $files['path'] != "tool/i18n/nls/lang.js");
          $filePath = ($isShortLang)?"tool/i18n/nls/*/lang.js":$files['path'];
          if(!isset($arrayFiles[$filePath])){
            $arrayFiles[$filePath]=$files;
            $title = ($isShortLang)?$langTitle:'';
            $fileRevDates = isset($fileDates[$filePath]) ? $fileDates[$filePath] : '';
            echo '     <tr id="'.$table.'FileLine_('.$filePath.')" data-revdates="'.$fileRevDates.'" class="'.$lineClass.'" onclick="updateRevisionSelectedLine(null, null, \''.$filePath.'\', \''.$table.'\')">';
            echo '       <td title="'.$title.'" class="updateSubData '.$table.'Files" value="'.$filePath.'">'.$filePath.'</td>';
            echo '     </tr>';
          }else{
            continue;
          }
        }
      }
      echo '      </table>';
    }
    echo '      </div>';
    echo '    </td>';
    echo '  </tr>';
    echo '</table>';
  }
  
  public static function drawUpdateTypeTable($table){
  	$updateType = 'manual';
  	if($table == 'version'){
  	  $updateType = Parameter::getGlobalParameter('versionUpdateType');
  	}else if($table == 'revision'){
  	  $updateType = Parameter::getGlobalParameter('revisionUpdateType');
  	}
  	if(!pq_trim($updateType)){
  	  $updateType = 'manual';
  	}
  	$display = ($updateType == 'manual')?'display:none':'';
    $scope = ($table == 'version')?'SubscriptionUpdateVersion':'SubscriptionUpdateRevision';
    echo '<table sytle="'.$display.'">';
    echo '  <tr>';
    echo '    <td style="width:225px;" class="label">'.i18n("updateFrequency"). Tool::getDoublePoint().'</td>';
    echo '    <td>';
    echo '        <div id="'.$table.'UpdateFrequency" name="'.$table.'UpdateFrequency">';
    echo            CronExecution::drawCronExecutionDefintion($scope);
    echo '        </div>';
    echo '    </td>';
    echo '  </tr>';
    echo '</table>';
  }
  
  public static function drawRequirementForUpdateTable($table){
  	$statusApp=Parameter::getGlobalParameter('applicationStatus');
  	if (!trim($statusApp)) {$statusApp='Open';}
  	$audit=New Audit();
  	$cpt=$audit->countSqlElementsFromCriteria(array('idle'=>'0')); //Number of user connected, need to have just one to confirm installation, the administrator
    if($table != 'current'){
      echo '<table>';
      echo '  <tr height="32px" style="vertical-align: middle;">';
      echo '    <td align="right">';
      echo        i18n("setApplicationToClosed").' :';
      echo '    </td>';
      echo '    <td align="left">';
      if($statusApp=='Open'){
        echo '&nbsp;'.i18n("applicationIsNotClosed");
      }else{
        echo '<span style="color:#1DB25E">';
        echo '&nbsp;'.i18n("applicationIsClosed");
        echo '</span>';
      }
      echo '&nbsp;<button id="'.$table.'OpenCloseApp" dojoType="dijit.form.Button" showlabel="true" class="dynamicTextButton" '.((isNewGui())?'style="position:relative;top:-3px"':'').'>';
      $operation="Closed";
      if ($statusApp!='Open') {$operation='Open';}
      echo i18n('setApplicationTo'.$operation);
      echo '  <script type="dojo/connect" event="onClick" args="evt">';
      echo '    subscriptionSetApplicationTo(\''.$operation.'\');';
      echo '    return false;';
      echo '  </script>';
      echo '</button>';
      echo '    </td>';
      echo '  </tr>';
      echo '  <tr height="32px" style="vertical-align: middle;">';
      echo '    <td align="right">';
      echo        i18n("applicationKickUser").' :';
      echo '    </td>';
      echo '    <td align="left">';
      if($cpt>1){
        echo '        &nbsp;'.i18n("applicationUserAreNotKick");
        echo '        &nbsp;<button id="'.$table.'DisconnectAll" dojoType="dijit.form.Button" showlabel="true" class="dynamicTextButton" '.((isNewGui())?'style="position:relative;top:-3px"':'').'>'.i18n('disconnectAll');
        echo '          <script type="dojo/connect" event="onClick" args="evt">';
        echo '               subscriptionDisconnectAll(true);';
        echo '                return false;';
        echo '          </script>';
        echo '      </button>';
      }else{
        echo '        <span style="color:#1DB25E">';
        echo '          &nbsp;'.i18n("applicationIsKickUser");
        echo '        </span>';
      }
      echo '    </td>';
      echo '  </tr>';
      if($table != 'revision'){
        echo '  <tr height="32px" style="vertical-align: middle;">';
        echo '    <td align="right">';
        echo          i18n("applicationBackup").' :';
        echo '    </td>';
        echo '    <td align="left">';
        echo '      <span style="color:#FF9933;">';
        echo '          &nbsp;'.i18n("applicationBackupMessage");
        echo '      </span>';
        echo '    </td>';
        echo '  </tr>';
      }
      if($table != 'version'){
        echo '  <tr><td><br/></td></tr>';
      	echo '  <tr>';
      	echo '    <td style="width:225px;" class="label"></td>';
      	echo '    <td>';
      	echo '      <button id="'.$table.'ForceUpdate" dojoType="dijit.form.Button" showlabel="true" class="dynamicTextButton" title="'.i18n('forceRevisionUpdateButton').'">';
      	echo '        <span>'.i18n('forceRevisionUpdateButton').'</span>';
      	echo '        <script type="dojo/connect" event="onClick" args="evt">';
      	echo '          downloadRevisionUpdate();';
      	echo '        </script>';
      	echo '      </button>';
      	echo '    </td>';
      	echo '  </tr>';
      }
      echo '</table>';
    }
  }
  
  public static function setLockFile($cron=false){
    $dir = dirname(__DIR__, 1);
    $lockFile=$dir.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."revision".DIRECTORY_SEPARATOR."LOCK";
    $handle=fopen($lockFile, 'w');
    $userId = ($cron)?0:getSessionUser()->id;
    fwrite($handle,'idUser='.$userId.'|startDateTime='.date('Y-m-d H:i'));
    fclose($handle);
  }
  
  public static function getLockFile() {
    $dir = dirname(__DIR__, 1);
    $lockFile=$dir.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."revision".DIRECTORY_SEPARATOR."LOCK";
    if(file_exists($lockFile)){
      $handle=fopen($lockFile, 'r');
      $line=fgets($handle);
      fclose($handle);
      $result=array();
      $arr=pq_explode('|',$line);
      foreach ($arr as $val) {
        $split=pq_explode('=',$val);
        if (count($split)==2) {
          $result[$split[0]]=$split[1];
        }
      }
      return $result;
    }else{
      return false;
    }
  }
  
  public static function deleteLockFile(){
    $dir = dirname(__DIR__, 1);
    $lockFile=$dir.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."revision".DIRECTORY_SEPARATOR."LOCK";
    if(file_exists($lockFile)){
      unlink($lockFile);
    }
  }
  
  public static function setPatchFile($revision){
    $dir = dirname(__DIR__, 1);
    $patchFile=$dir.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."PATCH";
    $handle=fopen($patchFile, 'w');
    fwrite($handle,$revision);
    fclose($handle);
  }
  
  public static function getPatchFile() {
    $dir = dirname(__DIR__, 1);
    $patchFile=$dir.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."PATCH";
    if(file_exists($patchFile)){
      $handle=fopen($patchFile, 'r');
      $line=fgets($handle);
      fclose($handle);
      return $line;
    }else{
      return false;
    }
  }
  
  public static function deletePatchFile(){
    $dir = dirname(__DIR__, 1);
    $patchFile=$dir.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."PATCH";
    if(file_exists($patchFile)){
      unlink($patchFile);
    }
  }

  public static function getRemoteFile($fileName, $code=null, $revisionFiles=null) {
    //ini_set('default_socket_timeout', 5); // Very short timeout
    ini_set('default_socket_timeout', 10); // Extend Timeout to avoid issue
    $proxy=Parameter::getGlobalParameter("paramProxy");
    $proxyUser=Parameter::getGlobalParameter("paramProxyUser");
    $proxyPassword=Parameter::getGlobalParameter("paramProxyPassword");
    if (!$code) $code = Parameter::getGlobalParameter('subscriptionCode');
    $mac=System::getUniqueCode();
    $userLang = getSessionValue('currentLocale');
    $lang=pq_substr($userLang,0,2);
    $revision=Parameter::getGlobalParameter('lastRevisionInstalled');
    $version=Sql::getDbVersion();
    $resource=New Resource();
    $cptUser=$resource->countSqlElementsFromCriteria(array('isUser'=>'1','idle'=>'0')); //Number of user
    $dataContent=($code)?"subscriptionCode=$code&subscriptionMac=$mac&lang=$lang&lastRevision=$revision&currentVersion=$version&nbUser=$cptUser":"currentVersion=$version";
    if($revisionFiles){
      $dataContent.="&fileName=$revisionFiles";
    }
    if (isset($proxy)) {
      if (isset($proxyUser) and $proxyUser and isset($proxyPassword) and $proxyPassword) {
        $auth = base64_encode("$proxyUser:$proxyPassword");
        $aContext = array(
            'http' => array(
                'method'=>'POST',
                'proxy' => $proxy,
                'timeout' => 60,
                'request_fulluri' => true,
                'header' => "Content-Type: application/x-www-form-urlencoded\r\n".
                            "Proxy-Authorization: Basic $auth",
                'content'=>$dataContent,
            ),
        );
      } else {
        $aContext = array(
            'http' => array(
                'method'=>'POST',
                'proxy' => $proxy,
                'timeout' => 60,
                'request_fulluri' => true,
                'header'  => 'Content-type: application/x-www-form-urlencoded',
                'content'=>$dataContent,
            ),
        );
      }
      $cxContext = stream_context_create($aContext);
    } else {
      $cxContext=null;
    }
    enableCatchErrors();
    $tryCount=0;
    $fileContent=false;
    while (! $fileContent and $tryCount<3) {
      $tryCount++;
      ini_set('default_socket_timeout', $tryCount*10); 
      $fileContent=file_get_contents($fileName,false,$cxContext);
    }
    return $fileContent;
    disableCatchErrors();
  }
  

  public static function displayInstallationList($location) {
    if ($location=='local') {
      $files=self::installAutoGetZipList();
    } else if ($location=='remote') {
      $files=array();
    } else {
      return; // unknown location
    }
    if (count($files)==0) {
      echo '<tr><td class="display" width="100%" colspan="6" style="text-align:center">';
      echo '<br/><i>'.i18n("installAutoNoInstallationAvailable").'</i></td></tr>';
    } else {
      echo '<tr >';
      echo '<td style="width:5%">&nbsp;</td>';
      echo '<td style="width:10%" class="noteHeader smallButtonsGroup"></td>';
      echo '<td class="noteHeader">'.i18n("colFile").'</td>';
      echo '<td style="width:15%" class="noteHeader">'.i18n("colDate").'</td>';
      echo '<td style="width:10%" class="noteHeader">'.i18n("colSize").'</td>';
      echo '<td style="width:5%">&nbsp;</td>';
      echo '</tr>';
      foreach ($files as $file) {
        echo '<tr>';
        echo '<td></td>';
        echo '<td class="noteData" style="text-align:center;white-space:nowrap"  >';
        echo '<a '; echo 'onClick="installAutoInstall(\''.$file['name'].'\');"title="' . i18n('installAutoInstall') . '"'; echo '>';
        echo formatSmallButton('Add');
        echo '</a>';
        echo '<a '; echo 'onClick="installAutoDeleteFile(\''.$file['name'].'\');"title="' . i18n('installAutoButtonDelete') . '"'; echo '>';
        echo formatSmallButton('Remove');
        echo '</a>';
        echo '</td>';
        echo '<td class="noteData">'.$file['name'].'</td>';
        echo '<td class="noteData" style="text-align:center">'.htmlFormatDate(pq_substr($file['date'],0,10),true).'</td>';
        echo '<td class="noteData" style="text-align:center">'.htmlGetFileSize($file['size']).'</td>';
        echo '<td></td>';
        echo '</tr>';
      }
    }
  }
  
  public static function installAutoGetZipList($oneOnlyFile=null) {
    $error='';
    $dir="..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version";
    $mk=true;
    if (!file_exists($dir)) {
      $mk = mkdir($dir,0777,true);
    }
    if (!$mk or ! is_dir($dir)) {
      traceLog ("installAutoGetZipList() - directory '$dir' does not exist");
      $error="installAutoGetZipList() - directory '$dir' does not exist";
    }
    if (! $error) {
      $handle = opendir($dir);
      if (! is_resource($handle)) {
        traceLog ("installAutoGetZipList() - Unable to open directory '$dir' ");
        $error="installAutoGetZipList() - Unable to open directory '$dir' ";
      }
    }
    $files=array();
    while (!$error and ($file = readdir($handle)) !== false) {
      if ($file == '.' || $file == '..' || $file=='index.php') {
        continue;
      }
      $filepath = ($dir == '.') ? $file : $dir . DIRECTORY_SEPARATOR . $file;
      if (is_link($filepath)) {
        continue;
      }
      if ($oneOnlyFile and $oneOnlyFile!=$file) {
        continue;
      }
      if (is_file($filepath) and pq_strtolower(pq_substr($file,-4))=='.zip') {
        $fileDesc=array('name'=>$file,'path'=>$filepath);
        $dt=filemtime ($filepath);
        $date=date('Y-m-d H:i',$dt);
        $fileDesc['date']=$date;
        $fileDesc['size']=filesize($filepath);
        $files[]=$fileDesc;
      }
    }
    if (! $error) closedir($handle);
    return $files;
  }
  
  public static function installAutoGetZipListTmp($oneOnlyFile=null) {
    $error='';
    $dir="..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version".DIRECTORY_SEPARATOR."tmp";
    $mk=true;
    if (!file_exists($dir)) {
      $mk = mkdir($dir,0777,true);
    }
    if (!$mk or ! is_dir($dir)) {
      traceLog ("installAutoGetZipListTmp() - directory '$dir' does not exist");
      $error="installAutoGetZipListTmp() - directory '$dir' does not exist";
    }
    if (! $error) {
      $handle = opendir($dir);
      if (! is_resource($handle)) {
        traceLog ("installAutoGetZipList() - Unable to open directory '$dir' ");
        $error="installAutoGetZipList() - Unable to open directory '$dir' ";
      }
    }
    $files=array();
    while (!$error and ($file = readdir($handle)) !== false) {
      if ($file == '.' || $file == '..' || $file=='index.php') {
        continue;
      }
      $filepath = ($dir == '.') ? $file : $dir . DIRECTORY_SEPARATOR . $file;
      if (is_link($filepath)) {
        continue;
      }
      if ($oneOnlyFile and $oneOnlyFile!=$file) {
        continue;
      }
      if (is_file($filepath) and pq_strtolower(pq_substr($file,-4))=='.zip') {
        $fileDesc=array('name'=>$file,'path'=>$filepath);
        $dt=filemtime ($filepath);
        $date=date('Y-m-d H:i',$dt);
        $fileDesc['date']=$date;
        $fileDesc['size']=filesize($filepath);
        $files[]=$fileDesc;
      }
    }
    if (! $error) closedir($handle);
    return $files;
  }
  
  public static function getFileInfo($url){
    if (!$url) {
      errorLog("file transfer issue : cannot get correct url");
      echo i18n('installAutoErrorDownload').'<br/>(incorrect url = \''.$url.'\')';
    }
    $ch = curl_init($url);
    $proxy=Parameter::getGlobalParameter("paramProxy");
    $proxyUser=Parameter::getGlobalParameter("paramProxyUser");
    $proxyPassword=Parameter::getGlobalParameter("paramProxyPassword");
    if (preg_match('`^https://`i', pq_nvl($url))) {
      curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
      curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
    }
    if (isset($proxy) and $proxy) {
      $split=explode("://",$proxy);
      if (count($split)>1) $proxy=$split[1];
      curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
      curl_setopt($ch, CURLOPT_TIMEOUT, 10);
      curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);
      curl_setopt($ch, CURLOPT_PROXY, $proxy);
      curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
      curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
      //curl_setopt($ch, CURLOPT_HTTPPROXYTUNNEL, true);
      if (isset($proxyUser) and $proxyUser and isset($proxyPassword) and $proxyPassword) {
        $proxyauth="$proxyUser:$proxyPassword";
        curl_setopt($ch, CURLOPT_PROXYUSERPWD, $proxyauth);
      }
    } else {
      curl_setopt( $ch, CURLOPT_NOBODY, true );
      curl_setopt( $ch, CURLOPT_HEADER, false );
      curl_setopt( $ch, CURLOPT_RETURNTRANSFER, false );
      curl_setopt( $ch, CURLOPT_FOLLOWLOCATION, true );
      curl_setopt( $ch, CURLOPT_MAXREDIRS, 3 );
    }
    curl_exec( $ch );
    $headerInfo = curl_getinfo( $ch );
    curl_close( $ch );
    return $headerInfo;
  }
  
  public static function fileDownload($url, $destination){
    $dir="..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version".DIRECTORY_SEPARATOR."tmp";
    $mk = true;
    if (!file_exists($dir)) {
      $mk = mkdir($dir,0777,true);
    }
    if($mk){
      $fp = fopen ($destination, 'w+');
      $ch = curl_init();
      $proxy=Parameter::getGlobalParameter("paramProxy");
      $proxyUser=Parameter::getGlobalParameter("paramProxyUser");
      $proxyPassword=Parameter::getGlobalParameter("paramProxyPassword");
      if (preg_match('`^https://`i', pq_nvl($url))) {
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
      }
      curl_setopt( $ch, CURLOPT_RETURNTRANSFER, false );
      curl_setopt( $ch, CURLOPT_URL, $url );
      curl_setopt( $ch, CURLOPT_BINARYTRANSFER, true );
      curl_setopt($ch, CURLOPT_TIMEOUT, 1000);
      curl_setopt( $ch, CURLOPT_CONNECTTIMEOUT, 1000);
      if (isset($proxy) and $proxy) {
        $split=explode("://",$proxy);
        if (count($split)>1) $proxy=$split[1];
        //curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
        curl_setopt($ch, CURLOPT_PROXY, $proxy);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
        //curl_setopt($ch, CURLOPT_HTTPPROXYTUNNEL, true);
        if (isset($proxyUser) and $proxyUser and isset($proxyPassword) and $proxyPassword) {
          $proxyauth="$proxyUser:$proxyPassword";
          curl_setopt($ch, CURLOPT_PROXYUSERPWD, $proxyauth);
        }
      } else {
        curl_setopt( $ch, CURLOPT_RETURNTRANSFER, false );
      }
      curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
      curl_setopt( $ch, CURLOPT_FILE, $fp );
      curl_exec( $ch );
      curl_close( $ch );
      fclose( $fp );
      if (filesize($destination) > 0) return true;
    }else{
      errorLog("file download issue : can't create $dir");
      return "file download issue : can't create $dir";
    }
  }
  
  public static function load($file) {
    global $globalCatchErrors;
    traceLog ( "New installation found : " . $file ['name'] );
    $zipFile = $file ['path'];
    $versionFile = self::getVersionFile ( $zipFile );
    if ($versionFile == - 1)
      return i18n ( 'installAutoFindVersionError' );
    $V1 = ltrim ( Parameter::getGlobalParameter ( "dbVersion" ), 'V' );
    $V2 = ltrim ( $versionFile, 'V' );
    $versionCompare = version_compare ( $V1, $V2 );
    if ($versionCompare > 0)
      return i18n ( 'installAutoCompareVersionError' );
    $result = "OK";
    // unzip plugIn files
    $zip = new ZipArchive ();
    $globalCatchErrors = true;
    $res = $zip->open ( $zipFile );
    if ($res === TRUE) {
      $res = $zip->extractTo ( "..".DIRECTORY_SEPARATOR );
      if ($res !== TRUE) {
        $zip->close ();
        return i18n ( 'installAutoRightAcess', Array (
            i18n ( 'installAutoRightZip' )
        ) );
      }
      $zip->close ();
      $returnCopy = self::recurseCopy ( "..".DIRECTORY_SEPARATOR."projeqtor".DIRECTORY_SEPARATOR, "..".DIRECTORY_SEPARATOR );
      if (is_string ( $returnCopy )) {
        return i18n ( 'installAutoRightAcess', Array (
            $returnCopy
        ) );
      }
      $delTree1 = self::delTree ( "..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version", false );
      if (is_string ( $delTree1 )) {
        return i18n ( 'installAutoRightAcess', Array (
            $delTree1
        ) );
      }
      $delTree2 = self::delTree ( "..".DIRECTORY_SEPARATOR."projeqtor".DIRECTORY_SEPARATOR."" );
      if (is_string ( $delTree2 )) {
        return i18n ( 'installAutoRightAcess', Array (
            $delTree2
        ) );
      }
      traceLog ( "Installation unzipped succefully" );
      return $result;
    }
    if ($res !== TRUE) {
      $result = i18n ( 'pluginUnzipFail', array (
          $zipFile,
          $zipFile
      ) );
      errorLog ( "RevisionUpdate::load() : $result" );
      return $result;
    }
  }
  
  public static function getVersionFile($file) {
    $zip = new ZipArchive ();
    $globalCatchErrors = true;
    $res = $zip->open ( $file );
    $fileInZip = "";
    if ($res === TRUE) {
      $idx = $zip->locateName ( 'projeqtor.php', ZIPARCHIVE::FL_NODIR );
      $fileInZip = $zip->getFromIndex ( $idx );
    }
    if (pq_strpos ( $fileInZip, '$version = "' ) !== false) {
      $size = 0;
      while ( pq_substr ( $fileInZip, pq_strpos ( $fileInZip, '$version = "' ) + 12 + $size, 1 ) != '"' ) {
        $size ++;
      }
      return pq_substr ( $fileInZip, pq_strpos ( $fileInZip, '$version = "' ) + 12, $size );
    } else 	if (pq_strpos ( $fileInZip, '$version="' ) !== false) {
      $size = 0;
      while ( pq_substr ( $fileInZip, pq_strpos ( $fileInZip, '$version="' ) + 10 + $size, 1 ) != '"' ) {
        $size ++;
      }
      return pq_substr ( $fileInZip, pq_strpos ( $fileInZip, '$version="' ) + 10, $size );
    } else {
      return - 1;
    }
  }
  
  public static function recurseCopy($source, $dest) {
    if (is_dir ( $source )) {
      $dir_handle = opendir ( $source );
      while ( $file = readdir ( $dir_handle ) ) {
        if ($file != "." && $file != "..") {
          if (is_dir ( $source . DIRECTORY_SEPARATOR . $file )) {
            if (! is_dir ( $dest . DIRECTORY_SEPARATOR . $file )) {
              mkdir ( $dest . DIRECTORY_SEPARATOR . $file );
            }
            self::recurseCopy ( $source . DIRECTORY_SEPARATOR . $file, $dest . DIRECTORY_SEPARATOR . $file );
          } else {
            copy ( $source . DIRECTORY_SEPARATOR . $file, $dest . DIRECTORY_SEPARATOR . $file );
          }
        }
      }
      closedir ( $dir_handle );
    } else {
      copy ( $source, $dest );
    }
  }
  
  public static function delTree($dir, $delFolder = true) {
    $files = array_diff ( scandir ( $dir ), array (
        '.',
        '..'
    ) );
    foreach ( $files as $file ) {
      $test = true;
      (is_dir ( $dir.DIRECTORY_SEPARATOR.$file ) and $dir != "..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version".DIRECTORY_SEPARATOR."tmp".DIRECTORY_SEPARATOR.".svn") ? self::delTree ( $dir.DIRECTORY_SEPARATOR.$file ) : $test = unlink ( $dir.DIRECTORY_SEPARATOR.$file );
      if (! $test) {
        return i18n ( 'installAutoRightDel', Array (
            $dir.DIRECTORY_SEPARATOR.$file
        ) );
      }
    }
    if ($delFolder)
      return rmdir ( $dir ) ? true : i18n ( 'installAutoRightDel', Array (
          $dir
      ) );
  }
  
  public static function downloadRevisionFiles($arrayRevisionUpdate, $filesList, $cron=false){
    if(count($filesList) > 0){
      $dir = dirname(__DIR__, 1);
      $root=$dir.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."revision".DIRECTORY_SEPARATOR."tmp".DIRECTORY_SEPARATOR;
      if (!file_exists($root)) {
        $mk = mkdir($root,0777,true);
      }else{
//        $tmpDir = opendir( $root );  // ouvre le répertoire
//        $files = readdir( $tmpDir );
//        while ( $files = readdir( $tmpDir ) ) {
//          traceLog($files);
//          unlink( $tmpDir.DIRECTORY_SEPARATOR.$files );  // supprime chaque fichier du répertoire
//        }
//        closedir( $tmpDir );
        purgeFiles($root, null, true);
      }
      self::setLockFile($cron);
      $code = Parameter::getGlobalParameter('subscriptionCode');
      $version=Sql::getDbVersion();
      $nameFile = 'revisionUpdate';
      foreach ($filesList as $filePath=>$filesInfo){
        //$filePathName = pq_str_replace("/", "\\", $filePath);
        $filePathRoot = pq_str_replace($filesInfo['name'], "", $filePath);
        if (!file_exists($root.$nameFile.DIRECTORY_SEPARATOR.$filePathRoot)) {
          $mk = mkdir($root.$nameFile.DIRECTORY_SEPARATOR.$filePathRoot,0777,true);
        }
        $fp = fopen ($root.$nameFile.DIRECTORY_SEPARATOR.$filePath, 'w+');
        $remoteFile=self::getRemoteFile("https://subscription.projeqtor.org/getFile.php", $code, $filePath);
        if ($remoteFile) fwrite($fp,$remoteFile);
        else {
          fclose( $fp );
          errorLog("Cannot get remote file $filePath - install cancelled");
          return i18n('intallRevisionUpdateError').'<br/><br/>'.i18n('errorXhrPostMessage');
        }
        fclose( $fp );
      }
      return self::zipFiles($arrayRevisionUpdate);
    }
  }

  public static function purgeDir($dir, $removeDirs=true) {
    $root = dirname(__DIR__, 1);
    $root=$root.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."revision".DIRECTORY_SEPARATOR."tmp";
    if (! is_dir($dir)) {
      return;
    }
    $handle = opendir($dir);
    if (! is_resource($handle)) {
      return;
    }
    while (($file = readdir($handle)) !== false) {
      if ($file == '.' || $file == '..' || $file=='.svn') {
        continue;
      }
      $filepath = $dir == '.' ? $file : $dir . DIRECTORY_SEPARATOR . $file;
      if (is_link($filepath)) {
        continue;
      }
      if (is_file($filepath)) {
        unlink($filepath);
      } else if (is_dir($filepath)) {
        self::purgeDir($filepath, $removeDirs);
      }
    }
    if ($removeDirs and $dir != $root) {
      rmdir($dir);
    }
    closedir($handle);
  }
  
  public static function zipFiles($arrayRevisionUpdate) {
    $version=Sql::getDbVersion();
    $root = dirname(__DIR__, 1);
    $nameFile='revisionUpdate';
    $lastestRevision = Parameter::getGlobalParameter('lastRevisionInstalled');
    foreach ($arrayRevisionUpdate as $revisionId=>$updates){
      if(intval(pq_substr($revisionId, 1)) > $lastestRevision)$lastestRevision = intval(pq_substr($revisionId, 1));
    }
    $nameFileZip = $nameFile.$lastestRevision.'.zip';
    $tmpDir=$root.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."revision".DIRECTORY_SEPARATOR."tmp";
    $tmpDirZip=$tmpDir.DIRECTORY_SEPARATOR.$nameFile;
    $outDirZip=$root.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."revision".DIRECTORY_SEPARATOR;
    $zipFile=$outDirZip.$nameFileZip;
    if (file_exists($zipFile)) unlink($zipFile);
    $zip=new ZipArchive();
    $ret=$zip->open($zipFile, ZIPARCHIVE::CREATE | ZIPARCHIVE::OVERWRITE);
    $Directory = new RecursiveDirectoryIterator($tmpDirZip);
    $Iterator = new RecursiveIteratorIterator($Directory);
    $files = new RecursiveIteratorIterator($Directory, RecursiveIteratorIterator::SELF_FIRST);
    foreach ($files as $file) {
      $fileFullName=realpath($file);
      //$file = pq_str_replace('\\', '/', $file);
      $file=pq_substr($file,pq_strlen($tmpDirZip)+1);
      $fileName=basename($file);
      if (pq_substr($fileName,0,1)=='.') continue;
      if (is_dir($fileFullName) === true) {
        $zip->addEmptyDir($file);
      } else if (is_file($fileFullName) === true) {
        $content=file_get_contents($fileFullName);
        $zip->addFromString($file, $content);
      }
    }
    $result = $zip->close();
    self::purgeDir($tmpDir);
    return $result;
  }
  
  public static function installRevisionUpdate($arrayRevisionUpdate){
    $result = '';
    $resultUpdate = '';
    Sql::beginTransaction();
    setSessionValue('installRevision', 'true');
    $lastestRevision = Parameter::getGlobalParameter('lastRevisionInstalled');
    foreach ($arrayRevisionUpdate as $revisionId=>$updates){
      if(intval(pq_substr($revisionId, 1)) > $lastestRevision)$lastestRevision = intval(pq_substr($revisionId, 1));
    }
    // unzip plugIn files
    $zip = new ZipArchive ();
    $globalCatchErrors = true;
    $root = dirname(__DIR__, 1);
    $outDirZip=$root.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."revision".DIRECTORY_SEPARATOR;
    $nameFileZip = 'revisionUpdate'.$lastestRevision.'.zip';
    $zipFile=$outDirZip.$nameFileZip;
    $res = $zip->open ( $zipFile );
    if ($res === TRUE) {
      $res = $zip->extractTo ($root);
      if ($res !== TRUE) {
        $zip->close ();
        $result=i18n('intallRevisionUpdateError').'<input type="hidden" id="lastSaveId" value="" /><input type="hidden" id="lastOperation" value="update" /><input type="hidden" id="lastOperationStatus" value="INVALID" />';
        return '<div class="messageINVALID" >'.$result.'</div>';
      }else{
        foreach ($arrayRevisionUpdate as $revisionId=>$updates){
          if(intval(pq_substr($revisionId, 1)) > $lastestRevision)$lastestRevision = intval(pq_substr($revisionId, 1));
          $revision = RevisionUpdate::getSingleSqlElementFromCriteria('RevisionUpdate', array("revisionId"=>$revisionId));
          $jonFiles['files'] = array();
          foreach ($updates['files'] as $files){
            array_push($jonFiles['files'], array("name"=>$files['name'], "path"=>$files['path']));
          }
          $revision->files = json_encode($jonFiles);
          $jonTickets['tickets'] = array();
          foreach ($updates['tickets'] as $tickets){
            array_push($jonTickets['tickets'], array("id"=>$tickets['id'], "name"=>$tickets['name'], "url"=>$tickets['url']));
          }
          $revision->tickets = json_encode($jonTickets);
          if(!$revision->id){
            $revision->revisionId = $revisionId;
            $revision->version = $updates['version'];
            $revision->date = date('Y-m-d H:i:s');
          }
          $resultUpdate = $revision->save();
          if(getLastOperationStatus($resultUpdate) != 'OK' and getLastOperationStatus($resultUpdate) != 'NO_CHANGE'){
            $result = $resultUpdate;
          }
        }
        $zip->close ();
        if(!$result){
          $result=i18n('revisionUpdateSuccessfull').'<input type="hidden" id="lastSaveId" value="" /><input type="hidden" id="lastOperation" value="update" /><input type="hidden" id="lastOperationStatus" value="OK" />';
          Parameter::storeGlobalParameter('lastRevisionInstalled', pq_str_replace('lastRevision=','',$lastestRevision));
          self::setPatchFile($lastestRevision);
        }else{
          $nameZipFiles='revisionUpdate'.$lastestRevision;
          unlink($root.DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."revision".DIRECTORY_SEPARATOR.$nameZipFiles.".zip");
        }
        displayLastOperationStatus($result);
      }
      if (file_exists($zipFile)) unlink($zipFile);
      self::deleteLockFile();
      $user = getSessionUser();
      $user->_arrayRevisionUpdate = array();
      if (Cron::check()=='running') Cron::restart();
      return $result;
    }else{
      enableCatchErrors();
      enableSilentErrors();
      if ($zipFile) @$zip->close ();
      disableSilentErrors();
      disableCatchErrors();
      errorLog("Cannot open zip file $zipFile");
      $result=i18n('intallRevisionUpdateError').'<input type="hidden" id="lastSaveId" value="" /><input type="hidden" id="lastOperation" value="update" /><input type="hidden" id="lastOperationStatus" value="INVALID" />';
      return '<div class="messageINVALID" >'.$result.'</div>';
    }
  }
  public static function finalizeMigration() {
    chdir("../db");
    global $version, $svnRevision, $build,$cronnedScript;
    $version=RevisionUpdate::getCurrentVersion();
    include("maintenance.php");
    chdir("../tool");
    if ($cronnedScript) Cron::autoRestart();
  }
  public static function getCurrentVersion(){
    $projFile=file_get_contents('../tool/projeqtor.php');
    $posVers=pq_strpos($projFile,'$version');
    $versStr=pq_substr($projFile,$posVers,25);
    $splitVers=explode('"',$versStr);
    $version=$splitVers[1];
    return $version;
  }
}
?>