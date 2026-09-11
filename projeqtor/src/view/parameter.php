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
 * List of parameter specific to a user.
 * Every user may change these parameters (for his own user only !).
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/view/parameter.php');

$type=$_REQUEST['type'];
$criteriaRoot=array();
$user=getSessionUser();
$manual=pq_ucfirst($type);

$collapsedList=Collapsed::getCollaspedList();

$parameterList=Parameter::getParamtersList($type);

$parameterSearchList=array();

$codeTab = '';
$codeSection = '';
foreach ($parameterList as $paramCode=>$paramType){
  if($paramType == 'tab' and $codeTab != $paramCode){
    $codeTab=pq_str_replace("tab", "", $paramCode);
  }
  if($paramType == 'section' and $codeSection != $paramCode){
    $codeSection=$paramCode;
  }
  if(!isset($parameterSearchList[$codeTab])){
    $parameterSearchList[$codeTab]=array();
  }
  if(!isset($parameterSearchList[$codeTab][$codeSection])){
    $parameterSearchList[$codeTab][$codeSection]=array();
  }
  if($paramType != 'tab' and $paramType != 'section' and $paramType != 'newColumn' and $paramType != 'newColumnFull'){
    $parameterSearchList[$codeTab][$codeSection][]=$paramCode;
  }
}

switch ($type) {
	case ('userParameter'):
		$criteriaRoot['idUser']=$user->id;
		$criteriaRoot['idProject']=null;
		break;
	case ('projectParameter'):
		$criteriaRoot['idUser']=null;
		$criteriaRoot['idProject']=null;
		break;
	case ('globalParameter'):
		$criteriaRoot['idUser']=null;
		$criteriaRoot['idProject']=null;
		break;
	case ('habilitation'):
	case ('habilitationReport'):
	case ('accessRight'):
	case ('accessRightNoProject'):
	case ('habilitationOther'):
		break;
	default:
		traceHack("parameter : unknown parameter type '$type'");
		exit;		 
}
Security::checkDisplayMenuForUser(pq_ucfirst($type));
/** =========================================================================
 * Design the html tags for parameter page depending on list of paramters
 * defined in $parameterList
 * @param $objectList array of parameters with format
 * @return void
 */ 

function drawTableFromObjectList($objectList) { 
  global $criteriaRoot, $type, $collapsedList, $parameterList, $parameterSearchList;
	$displayWidth='98%';
	$longTextWidth="500px";
	$arrayReadOnly=array();
	if ($type=='globalParameter' and (Parameter::getGlobalParameter('imputationUnit')=='hours' or Parameter::getGlobalParameter('workUnit')=='hours') ) {
	  $work=new Work();
	  $cpt=$work->countSqlElementsFromCriteria(array());
	  if ($cpt>0) {
	    $arrayReadOnly['dayTime']=true;
	  }
	}
	$paramSelectedTab=($type=='globalParameter')?Parameter::getUserParameter('globalParameterSelectedTab'):'tabDisplay';
	if(!$paramSelectedTab or $paramSelectedTab=="tabSearch"){
	  $paramSelectedTab=($type=='globalParameter')?'tabWork':'tabDisplay';
	}
	if (pq_array_key_exists('destinationWidth',$_REQUEST)) {
	  $width=$_REQUEST['destinationWidth'];
	  $width-=30;
	  $displayWidth=$width.'px';
	  $longTextWidth=($width-348-((isNewGui())?70:0)).'px';
	  
	} else {
	  if (sessionValueExists('screenWidth')) {
	    $detailWidth = round((getSessionValue('screenWidth') * 0.8) - 15) ; // 80% of screen - split barr - padding (x2)
	  } else {
	    $displayWidth='98%';
	  }
	}	
	$hasTab=false;
	$hasColumn=false;
	$hasSection=false;
	$requiredFields=array();
	$readonlyFields=array();
	if (SSO::isSamlEnabled()) {
	  $requiredFields=array('SAML_idpId','SAML_idpCert','SAML_SingleSignOnService','SAML_SingleLogoutService','SAML_attributeUid');
	}
	if (Parameter::getGlobalParameter('displayPoolsOnImputation') != 'NO') {
	  $readonlyFields=array('showPoolLinesToUpdateLeftWork');
	}
	$parameterList=array_filter($parameterList, function($k){
	  return $k != 'tab' and $k != 'section' and $k != 'newColumn';
	});
	$objectList = array('tabSearch'=>'tab')+$objectList;
	foreach($objectList as $code => $format) {
    $requiredClass='';
    $isReadOnly=false;
    if (in_array($code,$requiredFields)) $requiredClass= 'required';
    if (in_array($code,$readonlyFields)) $isReadOnly=true;
		$criteria=$criteriaRoot;
		$criteria['parameterCode']=$code;
		$helpTitle=pq_str_replace('&#13',"\n",i18n('help'. pq_ucfirst($code)));
		if ($code=='paramMailSmtpUsername' and Parameter::hostedSmtpDefault()) {
		  $helpTitle.="\n".i18n('refreshScreenForPassword');
		}
		// fetch the parameter saved in Database
		if ($type=='userParameter') {
			$obj=new Parameter();
			$obj->parameterCode=$code;
			$obj->parameterValue=Parameter::getUserParameter($code);
		} else if ($type=='globalParameter') {
			$obj=new Parameter();
			$obj->parameterCode=$code;
			$obj->parameterValue=Parameter::getGlobalParameter($code);
		} else {
		  $obj=SqlElement::getSingleSqlElementFromCriteria('Parameter', $criteria);
		}
		if ($type=='userParameter') { // user parameters may be stored in session
		  if (sessionValueExists($code)) {
				$obj->parameterValue=getSessionValue($code);
			}
			if ($code=='timeZone' and ! pq_trim($obj->parameterValue)) $obj->parameterValue=Parameter::getGlobalParameter('paramDefaultTimezone');
		}
		if ($format=='tab') {
		  if ($hasSection) {
		    echo '</table></div><br/>'; // close the section level
		  }
		  if ($hasColumn) { // close the column  level
		    echo '</td></tr></table>';
		  }
		  if ($hasTab) {
		    echo '</div>'; // close the tab level
		  } else {
		    echo '<div style="position: absolute; display: flex; align-items: center;margin : 0px 10px; top:15px; z-index:999">';
		    echo    formatIconNewGui('Search', 16);
		    echo '  <input type="text" id="parameterSearchFilterInput" placeholder="'.i18n('searchParameter').'" onFocus="filterParameter(this.value)" onkeyup="filterParameter(this.value)" style="border: 1px solid var(--color-medium); border-radius: 5px; margin: 0px 10px; padding: 5px;" />';
		    echo '  <div class="iconCancel iconSize16 imageColorNewGui" onclick="clearSearchInputParameter();" id="clearSearchInputParameter" style="cursor: pointer;display:none;"></div>';
		    echo '  <div class=":::::: " dojoType="dijit.form.DropDownButton" id="parameterSearchMenu" name="parameterSearchMenu" style="position:absolute;top:20px;left:5px;width:0px;height:0px;overflow:hidden;">';
        echo '    <div dojoType="dijit.TooltipDialog" id="dialogParameterSearch" tabindex="0" style="overflow:hidden">';
        echo '      <div class="title" style="margin: 5px 20px;border-bottom: 1px solid var(--color-reference);padding:5px;display:flex;" ><div style="padding-right:10px;">'.formatIconNewGui('Search', 22).'</div><div>'.i18n('searchParameter').'</div></div>';
        echo '      <div id="parameterSearchList" style="margin: 5px 20px;overflow-y:auto;overflow-x:hidden;max-height:600px;">';
        echo '        <div id="noSearchParamaterFound" style="font-style:italic;padding:5px;font-size:11pt;">'.i18n('noSearchParamaterFound').'</div>';
        foreach ($parameterSearchList as $paramTab => $paramSections){
          foreach ($paramSections as $paramSection => $paramCodes){
            $section=$type.'_'.$paramSection;
            echo '<div class="parameterSearchSection" id="section_'.$paramSection.'" onClick="selectSearchParameter(\''.$paramTab.'\',\''.$section.'\',null)" style="display:none;font-weight:bold;cursor:pointer;padding:5px;font-size:10pt;">'.i18n($paramSection).'</div>';
            foreach ($paramCodes as $paramCode){
              echo '      <div class="parameterSearchName" id="searchFor'.$paramCode.'" style="display:none;cursor:pointer;padding:5px 5px 5px 20px;font-size:9pt;" onClick="selectSearchParameter(\''.$paramTab.'\',\''.$section.'\',\''.$paramCode.'\')">'.i18n("param".ucfirst($paramCode));
              echo '        <input type="hidden" id="sectionFor'.$paramCode.'" name="sectionFor'.$paramCode.'" value="'.$paramSection.'" />';
              echo '        <input type="hidden" value="'.i18n($paramSection).'" />';
              echo '      </div>';
            }
          }
        }
        echo '      </div>';
		    echo '    </div>';
		    echo '  </div>';
        echo '</div>';
		    echo '<div dojoType="dijit/layout/TabContainer" id="parameterTabContainer" style="width: 100%; height: 100%;">'; // Start the tabContanier Level
		  }
		  $disabled = ($code == 'tabSearch')?'disabled':'';
		  $title = i18n($code);
		  $onShow = ($type=='globalParameter')?'saveDataToSession(\'globalParameterSelectedTab\',\''.$code.'\',true);':'';
		  if($code == 'tabSearch'){
		    $title = '';
		    $onShow = '';
		  }
		  echo '<div id="'.pq_substr($code,3).'" '.$disabled.' onShow="'.$onShow.'" dojoType="dijit/layout/ContentPane" title="'.$title.'" '.(($code != 'tabSearch' and $paramSelectedTab==$code)?'selected="true"':'').'>'; // New tab level
		  $hasTab=true;
		  $hasColumn=false;
		  $hasSection=false;
		} else if ($format=='newColumn' or $format=='newColumnFull') {
		  if ($hasSection) {
		    echo '</table></div><br/>'; // close the section level
		  }
		  if ($hasColumn) { // close the column level
		    echo '</td>';
		  } else {
		    echo '<table style="width:99%; margin-left:1%;vertical-align:top;"><tr style="height:100%">'; // Open the table column container
		  }
		  if ($format=='newColumn') {
		    echo '<td style="width:50%;vertical-align:top;">';
		  } else { // $format=='newColumnFull'
		    echo '</tr><tr><td colspan="2" style="width:50%;vertical-align:top;">';
		  }
		  $hasColumn=true;
		  $hasSection=false;
		} else if ($format=="section") { // New section
		  if ($hasSection) {
		    echo '</table></div>'; // close the section level
		  }
			echo '<br/>';
			$divName=$type.'_'.$code;
			echo '<div id="' . $divName . '" dojoType="dijit.TitlePane"';
			echo ' open="' . (pq_array_key_exists($divName, $collapsedList)?'false':'true') . '"';
			echo ' onHide="saveCollapsed(\'' . $divName . '\');"';
			echo ' onShow="saveExpanded(\'' . $divName . '\');"';
			echo ' title="' . i18n($code) . '" style="width:98%; position:relative;" tabindex="-1"';
			echo '>';
			echo '<table>';
			$hasSection=true;
	  } else {
	    if ($code !== 'paramLdap_port' && $code !== 'ldapFormatUri'){ // hide ldapFormatUri and ldapPort
		  echo ($code=='paramAttachmentNum' or $code=='paramAttachmentNumMail')?'<tr id="line_'.$code.'" hidden tabindex="-1"> ':'<tr id="line_'.$code.'" tabindex="-1"> '; // open the line level (must end with  a </td></tr>)
		  $message = $code == '_lib_inputMailboxMessage' ? 'width: 98%;text-align: left;' : '';
		  echo '<td class="crossTableLine"><label class="label largeLabel" id="label_'.$code.'" for="' . $code . '" '.((isNewGui())?' style="margin-top:-2px;'.$message.'" ':'').' title="' . $helpTitle . '">' 
		              . (($format!='photo')?i18n('param' . pq_ucfirst($code) ) . ((isNewGui())?'':' :').'&nbsp;':'')
		         .'</label></td><td style="position:relative">';
			if ($format=='list') {
				$listValues=Parameter::getList($code);
				echo '<select dojoType="dijit.form.FilteringSelect" class="input '.$requiredClass.'" name="' . $code . '" id="' . $code . '" ';
				if($code=='defaultProject') echo 'data-dojo-props="queryExpr: \'*${0}*\', autoComplete:false"';
				if ($isReadOnly) echo ' disabled ';
				echo autoOpenFilteringSelect();
				$listWidth='200';
				if (pq_substr($code,0,24)=='imputationOnlyIncomplete') $listWidth='350';
				echo ' title="' . $helpTitle. '" style="width:'.$listWidth.'px">';
				if ( ($type=='userParameter' and $code!='startPage') or $code=='versionNameAutoformat' or $code=='SAML_allow_login' or $code=='paramMailerType' or $code=='newGui' or $code=="displayPoolsOnImputation" or $code=='autoUpdateLeftWorkOnPool') {
					echo $obj->getValidationScript($code);
				}
				if($code=='defaultProject') {
				  echo "<option value='**' ".(($obj->parameterValue=='**')?'selected':'')." >".i18n('lastProject')."</option>";
				  echo "<option value='*' ".(($obj->parameterValue=='*')?'selected':'').">".i18n('allProjects')."</option>";
				  htmlDrawOptionForReference('idProject', ($obj->parameterValue!='**' and $obj->parameterValue!='*')?$obj->parameterValue:null, null, true);
				} else {
				foreach ($listValues as $value => $valueLabel ) {
					$selected = ($obj->parameterValue==$value)?'selected':'';
					$value=pq_str_replace(',','#comma#',$value); // Comma sets an isse (not selected) when in value
					echo '<option value="' . $value . '" ' . $selected . '>' . $valueLabel . '</option>';
				}
				}
				echo '</select>';
			} else if ($format=='time') {
				echo '<div dojoType="dijit.form.TimeTextBox" ';
				echo ' name="' . $code . '" id="' . $code . '"';
				echo ' title="' . $helpTitle . '"';
				echo ' type="text" maxlength="5" ';
				if (sessionValueExists('browserLocaleTimeFormat')) {
				  echo ' constraints="{timePattern:\'' . getSessionValue('browserLocaleTimeFormat') . '\'}" ';
				}
				echo ' style="width:50px; text-align: center;" class="input" ';
				echo ' value="T' . htmlEncode($obj->parameterValue) . '" ';
				echo ' hasDownArrow="false" ';
				echo ' >';
				echo $obj->getValidationScript($code);
				echo '</div>';
			} else if ($format=='number' or $format=='longnumber') {
				echo '<div dojoType="dijit.form.NumberTextBox" ';
				echo ' name="' . $code . '" id="' . $code . '"';
				echo ' title="' . $helpTitle . '"';
				echo ($format=='longnumber')?' style="width: 100px;" ':' style="width: 50px;" ';
				//echo ' constraints="{places:\'0\'}" ';
				echo ' class="input" ';
				if (isset($arrayReadOnly[$code])) echo " readonly ";
				echo ' value="' .  htmlEncode($obj->parameterValue)  . '" ';
				echo ' >';
				echo NumberFormatter52::completeKeyDownEvent($obj->getValidationScript($code));
				echo '</div>';
			}else if ($format=='text' or $format=='password') {
				echo '<div dojoType="dijit.form.TextBox" ';
				echo ' name="' . $code . '" id="' . $code . '"';
				echo ' title="' . $helpTitle . '"';
				if($code =='paramTryToHackObjectMail'){
				  echo 'style="width: 290px;" ';
// 				}elseif($code =='paramMailSmtpPassword' or $code =='paramLdap_search_pass' or $code=="cronCheckEmailsPassword"){
				}elseif($code =='paramMailSmtpPassword' or $code =='paramLdap_search_pass'){
				  echo 'style="width: 174px;" ';
 				}else{
				  echo ($code=='paramAttachmentMaxSize' or $code=='paramAttachmentMaxSizeMail')?' style="width: 100px;text-align: center;" ':' style="width: 200px;" ';
				}
				echo ' class="input '.$requiredClass.'" ';
				if ($format=='password') echo ' type="password" ';
				//florent
				if($code=='paramAttachmentMaxSize' or $code=='paramAttachmentMaxSizeMail'){
				 $valChar=1;
				 $char=Parameter::getGlobalParameter('paramAttachmentNum');
				 if($code=='paramAttachmentMaxSizeMail'){
				   $char=Parameter::getGlobalParameter('paramAttachmentNumMail');
				 }
				 
				    switch ($char) {
				 	  case "K":
				 	    $valChar=1024;
				 	  break;
				 	  case "M":
				 	    $valChar=1024*1024;
				 	  break;
				 	  case "G":
				 	   $valChar=1024*1024*1024;
				 	  break;
				 	  case "T":
				 	    $valChar=1024*1024*1024*1024;
				 	  break;
				    }
				   $numb= number_format(intval($obj->parameterValue)/$valChar,0,' ',' ');
				 echo ' value="' .  htmlEncode(strval($numb).$char) . '" ';
				}else{
				  $val = $obj->parameterValue;
// 				  if($code=="paramLdap_search_pass" or $code=="paramMailSmtpPassword" or $code=="cronCheckEmailsPassword"){
				  if($code=="paramLdap_search_pass" or $code=="paramMailSmtpPassword"){
				    $val = decryptPwd($val);
				  }
				  echo ' value="' .  htmlEncode($val) . '" ';
				}
				//end
				echo ' >';
				echo $obj->getValidationScript($code);
				echo '</div>';
				//gautier #Password
				if ($format=='password' and isNewGui()) {
				  echo '<div class="iconView imageColorNewGui iconSize22" style="cursor:pointer;float:right;position:relative;top:6px;margin-right:4px;" onClick="dojo.setAttr(\''.$code.'\',\'type\',((dojo.getAttr(\''.$code.'\',\'type\')==\'password\')?\'text\':\'password\'));" ></div>';
				  echo '</div>';
				}
				
		  }else if ($format=='display') {
		      if($code=="mailerTestMessage" or $code=="paramTryToHackMailList"){
		        echo '<div class="" style="width:212px;position:relative;min-height:18px">';
		      } else {
		        echo '<div class="" style="width:'.$longTextWidth.';position:relative;min-height:18px">';
		      }
				  echo '<input type="hidden" name="'.$code.'" id="'.$code.'" value="'.htmlEncode($obj->parameterValue).'"/>';
				  echo '<div id="'.$code.'_iconMessageMail" name="'.$code.'_iconMessageMail" style="display:none;right:0;position:absolute;pointer-events:none">';
				  if($code!="paramTryToHackMailList"){
				  echo '<a onclick="mailerTextEditor('.$code.');" id="mailerTextEditor" title="' . i18n('editMailerTestMessageIcon') . '">'.formatSmallButton('Edit').'</a>';
				  }
				  echo '</div>';
				  echo '<div style="word-break:break-all;background:white;color: #555555;margin: 5px 2px 5px 0px;padding: 2px 5px 6px 5px;border: 1px solid #d4d4d4;border-radius: 5px 5px 5px 5px;" name="'.$code.'_display" id="'.$code.'_display" onmouseover="displayImageEditMessageMail(\''.$code.'\');" onmouseout="hideImageEditMessageMail(\''.$code.'\');" onclick="mailerTextEditor(\''.$code.'\');"';
				  if($code=="mailerTestMessage"  or $code=="paramTryToHackMailList" ){
				   	echo ' style="word-wrap:break-word;width:200px;display:inline-block;min-height:18px" ';
				  } else {
				    echo ' style="width:'.$longTextWidth.';word-wrap:break-word;display:inline-block;min-height:18px" ';
				  }
				  echo " >";
				  echo '<div>';
				  echo ($obj->parameterValue)?$obj->parameterValue:"&nbsp;";
				  echo '</div>';
				  echo '</div>';
			}else if ($format=='longtext') {
			  if($code=='paramTryToHackUserList' or $code=='paramTryToHackMailList'){
			    if($code=="paramTryToHackUserList"){
			      echo '<input type="hidden" name="' . $code . '" id="' . $code . '" value="'.$obj->parameterValue.'"/>';
			      $code = $code.'Display';
			      echo '<textarea readOnly dojoType="dijit.form.Textarea" ';
			      echo ' name="' . $code . '" id="' . $code . '"';
			      echo ' title="' . $helpTitle . '"';
			      echo ' style="max-height:118px;background:white !important;width:300px;position:relative;min-height:18px;" onclick="selectResources(null,\'paramTryToHackUserList\',null)" ';
			      echo ' >';
			      $idAffectable = pq_explode(";", $obj->parameterValue);
			      $number = 1;
			      $countNumber = count($idAffectable);
			      foreach ($idAffectable as $myId){
			        if($number > 1 and $number <= $countNumber  ){echo ';';  echo "\n";}
			        echo SqlList::getNameFromId('Affectable', $myId);
			        $number++;
			      }
			      echo '</textarea>';
			      echo ' <div style="position:absolute;top:9px;left:270px;" class="roundedButton roundedIconButton generalColClass idProjectClass"><div class="imageColorNewGui iconToolbarSearch" onclick="selectResources(null,\'paramTryToHackUserList\',null)">  </div></div>';
			    }else{
			      echo '<textarea dojoType="dijit.form.Textarea" ';
			      echo ' name="' . $code . '" id="' . $code . '"';
			      echo ' title="' . $helpTitle . '"';
			      echo ' style="width:300px;position:relative;min-height:18px;" ';
			      echo ' class="input" ';
			      echo ' >';
			      echo $obj->parameterValue;
			      echo '</textarea>';
			    }
			  }else{
  				echo '<textarea dojoType="dijit.form.Textarea" ';
  				echo ' name="' . $code . '" id="' . $code . '"';
  				echo ' title="' . $helpTitle . '"';
  				echo ' style="width: '.$longTextWidth.';" ';
  				echo ' class="input" ';
  				echo ' >';
  				echo $obj->parameterValue;
  				//echo $obj->getValidationScript($code);
  				echo '</textarea>';
			  }
			} else if ($format=='photo') { // for user photo 
			  //echo "</td></tr>";
			  $user=getSessionUser();
			  echo '<input type="hidden" id="objectId" value="'.htmlEncode($user->id).'"/>';
			  echo '<input type="hidden" id="objectClass" value="User"/>';
			  echo '<input type="hidden" id="parameter" value="true"/>';
			  echo '<div style="position:relative;height:100px;width:120px;top:-20px;xleft:50px;">';
			    $imageHtml=$user->drawSpecificItem('image');
			    echo $imageHtml;
			  echo '</div>';
			} else if ($format=='specific') {
			  if ($code=='password') {
			    $title=i18n('changePassword');
			    echo '<button class="roundedVisibleButton" id="changePassword" dojoType="dijit.form.Button" showlabel="true"';
			    if (0) {
			      $result .= ' disabled="disabled" ';
			    }
			    echo ' title="' . $title . '" style="vertical-align: middle;">';
			    echo '<span>' . $title . '</span>';
			    echo '<script type="dojo/connect" event="onClick" args="evt">';
			    echo ' requestPasswordChange();';
			    echo '</script>';
			    echo '</button>';
			  } else if ($code=='markAlertsAsRead') {
			    $title=$helpTitle;
			    echo '<button class="roundedVisibleButton" id="markAlertsAsRead" dojoType="dijit.form.Button" showlabel="true"';
			    echo ' iconClass="imageColorNewGui iconNotification22 iconNotification iconSize22" ';
			    echo ' title="' . $title . '" style="vertical-align: middle;">';
			    echo '<span>' . i18n('paramMarkAlertsAsRead') . '</span>';
			    echo '<script type="dojo/connect" event="onClick" args="evt">';
			    echo ' maintenance("read","Alert");';
			    echo '</script>';
			    echo '</button>';
			  } else if ($code=='showSubscribedItems') {
			    $title=$helpTitle;
			    echo '<button class="roundedVisibleButton" id="showSubscribedItems" dojoType="dijit.form.Button" showlabel="true"';
			    echo ' iconClass="imageColorNewGui dijitButtonIcon dijitButtonIconSubscribe" ';
			    echo ' title="' . $title . '" style="vertical-align: middle;">';
			    echo '<span>' . i18n('showSubscribedItemsList') . '</span>';
			    echo '<script type="dojo/connect" event="onClick" args="evt">';
			    echo '  showSubscriptionList("'.getSessionUser()->id.'");';
			    echo '</script>';
			    echo '</button>'; 
			  } else if ($code=='team') {
			  	$usr=getSessionUser();
			  	$res=new Resource($usr->id);
			  	$team=new Team($res->idTeam);
			  	$teamName = $team->name;
			  	if(!$teamName)$teamName = ' - ';
			  	echo $teamName;
			  } else if ($code=='organization') {
			  	$usr=getSessionUser();
			  	$res=new Resource($usr->id);
			  	$orga=new Organization($res->idOrganization);
			  	$orgaName = $orga->name;
			  	if(!$orgaName)$orgaName = ' - ';
			  	echo $orgaName;
			  } else if ($code=='profile') {
			  	  $usr=getSessionUser();
			  	  $prof=new Profile($usr->idProfile);
			  	  echo i18n($prof->name);
			  } else if ($code=='mailerTest') {
			    $title=$helpTitle;
			    echo '<div style="vertical-align:top">';
			    echo '<button id="testMail" dojoType="dijit.form.Button" showlabel="false"';
			    echo ' class="detailButton" iconClass="dijitButtonIcon dijitButtonIconEmail " ';
			    echo ' title="' . $title . '" style="vertical-align: middle;">';
			    //echo '<span>' . i18n('paramMailerTest') . '</span>';
			    echo '<script type="dojo/connect" event="onClick" args="evt">';
			    echo '  showWait();';
			    echo '  dojo.byId("testEmailResult").innerHTML="";';
			    echo '  var callbackAfterSave=function(){var hide=function(){hideWait();};loadDiv("../tool/sendMailTest.php","testEmailResult",null,hide);};';
			    echo '  loadDiv("../tool/saveParameter.php","testEmailSaveResult", "parameterForm", callbackAfterSave);';
			    echo '</script>';
			    echo '</button>';
			    echo '<div id="testEmailResult" style="padding-left:10px;display:inline-block;"></div>';
			    echo '<div id="testEmailSaveResult" style="display:none;"></div>';
			    echo '</div>';
			  } else if ($code=='automaticPlanningDifferential' or $code=='automaticPlanningComplete' or $code=='automaticBaseline' or pq_strpos($code, 'imputationAlertCron') !== false) { 
			      if(pq_strpos($code, 'imputationAlertCron') !== false){
			          CronExecution::drawCronExecutionDefintion($code);
			      }else{
			          CronExecution::drawCronExecutionDefintion(pq_substr($code,9));
			      }
			  } else if ($code=='SAML_metadata') {         
			    echo '<div style="vertical-align:top">';
			    echo '<button id="getSpMetadata" dojoType="dijit.form.Button" showlabel="true"';
			    echo 'class="roundedVisibleButton" iconClass="dijitButtonIcon dijitButtonIconDisplay" ';
			    echo ' title="'.$helpTitle.'" ';
			    echo ' style="vertical-align: middle;">'.i18n("SAML_getSpMetadata");
			    //echo '<span>' . i18n('paramMailerTest') . '</span>';
			    echo '<script type="dojo/connect" event="onClick" args="evt">';
			    echo " window.open('".SSO::getSettingValue('entityId')."','projeqtorMetadata');";
			    echo '</script>';
			    echo '</button>';
			    echo '</div>';
			  } else if ($code=='SAML_spCertMessage') {
			    echo '<div style="vertical-align:top">';
			    echo i18n('SAML_spCertMessage');
			    echo '</div>';
			  } else if ($code=='skillsAlertCron'){
          echo '<div style="display: inline-block;">';
          echo CronExecution::drawCronExecutionDefintion('skillsAlertCron',false);
          echo '</div>';
			  }
			}else if($format=='color'){
			  if($code=='newGuiThemeColor') $theming="setColorTheming(this.value,dojo.byId('".$type."_newGuiThemeColorBis').value);";
			  if($code=='newGuiThemeColorBis') $theming="setColorTheming(dojo.byId('".$type."_newGuiThemeColor').value,this.value);";
			  if($type=='userParameter'){
			    if($code=='newGuiThemeColor') $theming="dojo.byId('menuUserColorPicker').value=this.value;".$theming;
			    if($code=='newGuiThemeColorBis') $theming="dojo.byId('menuUserColorPickerBis').value=this.value;".$theming;
			    echo '<input type="color" id="'.$type.'_'.$code.'" name="'.$type.'_'.$code.'" onInput="'.$theming.'" onChange="saveDataToSession(\''.$code.'\',this.value.substr(1),true);setGlobalNewGuiThemeColor(\''.$code.'\', this.value.substr(1));'.$theming.'" value="#'.$obj->parameterValue.'" style="height: 24px;width: 60px;border-radius: 5px 5px 5px 5px;" />';
			  }else{
			    echo '<input type="color" id="'.$type.'_'.$code.'" name="'.$type.'_'.$code.'" onInput="'.$theming.'" onChange="saveDataToSession(\''.$code.'\',this.value.substr(1));setGlobalNewGuiThemeColor(\''.$code.'\', this.value.substr(1));'.$theming.'" value="#'.$obj->parameterValue.'" style="height: 24px;width: 60px;border-radius: 5px 5px 5px 5px;" />';
			  }
			  echo '<input type="hidden" id="'.$code.'" name="'.$code.'" value="'.$obj->parameterValue.'"/>';
			  if ($code=='newGuiThemeColor') drawColorDefaultThemes($type.'_newGuiThemeColor',$type.'_newGuiThemeColorBis',52,70);
			}
			//if ($format!='photo') {
			echo '</td></tr>'; // close the line level
			//}
		}
	  }
	}
	
	if ($hasSection) echo '</table><br/></div><br/>'; // Close the Section level
	if ($hasColumn) echo '</td></tr></table>'; // Close the column level
	if ($hasTab) echo '</div></div>'; // Close the tab level and the tab container level
	echo '</div>'; // Tab container level
}
?>
<input
  type="hidden" name="objectClassManual" id="objectClassManual"
  value="<?php echo $manual;?>" />
<div class="container" dojoType="dijit.layout.BorderContainer">
<div id="parameterButtonDiv" class="listTitle" style="z-index:3;overflow:visible"
  dojoType="dijit.layout.ContentPane" region="top">
  <script type="dojo/connect" event="onShow" args="evt"><?php //Parameter::setDisplaySM();?></script>
<table width="100%" class="today projeqtorReference">
  <tr height="100%" style="vertical-align: middle;">
    <td width="50px" align="center"><?php echo formatIcon(pq_ucfirst($type), 32, null, true);?></td>
    <td><span class="title"><?php echo pq_str_replace(" ","&nbsp;",i18n('menu'.pq_ucfirst($type)))?>&nbsp;</span>
    </td>
    <td width="10px">&nbsp;</td>

    <td width="35px">
    <button id="saveParameterButton" dojoType="dijit.form.Button"
      showlabel="false"
      title="<?php echo i18n('buttonSaveParameters');?>"
      iconClass="dijitButtonIcon dijitButtonIconSave" class="detailButton">
        <script type="dojo/connect" event="onClick" args="evt">              
          submitForm("../tool/saveParameter.php"+addTokenIndexToUrl('?'),"resultDivMain", "parameterForm", true);
        </script>
    </button>
    <div dojoType="dijit.Tooltip" connectId="saveButton"><?php echo i18n("buttonSaveParameter")?></div>
    </td>
    <td style="position:relative;">
    </td>  
    <?php if($manual != 'UserParameter' and $manual != 'GlobalParameter'){?>
    <td width="35px">
    <button id="minusParameterButton" dojoType="dijit.form.Button"
      showlabel="false"
      title="<?php echo i18n('buttonMinusParameters');?>"
      iconClass="imageColorNewGui iconMinus" class="detailButton"> 
       <script type="dojo/connect" event="onClick" args="evt">           
          saveCollapsedMultiple=true;   
          dojo.query('.TitlePaneDisplay').forEach(function(node){
            var element = dijit.byId(node.id);
            element.set('open',false);
          });
          saveCollapsedMultiple=false;
      </script>
    </button>
    <div dojoType="dijit.Tooltip" connectId="minusButton"><?php echo i18n("buttonMinusParameter")?></div>
    </td>
    <td style="position:relative;">
    </td>     
     
    <td width="50px">
    <button id="plusParameterButton" dojoType="dijit.form.Button"
      showlabel="false"
      title="<?php echo i18n('buttonPlusParameters');?>"
      iconClass="imageColorNewGui iconPlus" class="detailButton"> 
       <script type="dojo/connect" event="onClick" args="evt">
          saveCollapsedMultiple=true;        
          dojo.query('.TitlePaneDisplay').forEach(function(node){
            var element = dijit.byId(node.id);
            element.set('open',true);
          });
          saveCollapsedMultiple=false;
       </script>
    </button>
    <div dojoType="dijit.Tooltip" connectId="plusParameterButton"><?php echo i18n("buttonplusParameter")?></div>
    </td>
    <?php }?>
    <td style="position:relative;">
    </td>
          
  </tr>
</table>
</div>

<div id="formDiv" dojoType="dijit.layout.ContentPane" region="center"
  style="overflow-y: auto; overflow-x: hidden;">
<form dojoType="dijit.form.Form" id="parameterForm" jsId="parameterForm"
  name="parameterForm" encType="multipart/form-data" action="" method="">
  <input type="hidden" name="parameterType" value="<?php echo $type;?>" />
  <?php 
  if ($type=='habilitation') {
  	htmlDrawCrossTable('menu', 'idMenu', 'profile', 'idProfile', 'habilitation', 'allowAccess', 'check', null,'idMenu') ;
  } else if ($type=='accessRight') {
  	htmlDrawCrossTable('menuProject', 'idMenu', 'profile', 'idProfile', 'accessRight', 'idAccessProfile', 'list', 'accessProfile', 'idMenu');
  } else if ($type=='accessRightNoProject') {
  	$titlePane="habilitation_ReadWritePrincipal";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('menuPrincipal') . '">';
  	htmlDrawCrossTable('menuReadWritePrincipal', 'idMenu', 'profile', 'idProfile', 'accessRight', 'idAccessProfile', 'list', 'accessProfileNoProject') ;
  	echo '</div><br/>';
  	if (Module::isModuleActive('moduleConfiguration')) {
    	$titlePane="habilitation_ReadWriteConfiguration";
    	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
    	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
    	echo ' id="' . $titlePane . '" ';
    	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
    	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
    	echo ' title="' . i18n('menuConfiguration') . '">';
    	htmlDrawCrossTable('menuReadWriteConfiguration', 'idMenu', 'profile', 'idProfile', 'accessRight', 'idAccessProfile', 'list', 'accessProfileNoProject') ;
    	//
      echo '</div><br/>';
    }
    if (Module::isModuleActive('moduleLocalization')) {
      $titlePane="habilitation_ReadWriteTranslation";
      echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
      echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
      echo ' id="' . $titlePane . '" ';
      echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
      echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
      echo ' title="' . i18n('menuLocalizationManagement') . '">';
      htmlDrawCrossTable('menuReadWriteLocalization', 'idMenu', 'profile', 'idProfile', 'accessRight', 'idAccessProfile', 'list', 'accessProfileNoProject') ;
    	echo '</div><br/>';
    }
  	$titlePane="habilitation_ReadWriteTool";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('menuTool') . '">';
  	htmlDrawCrossTable('menuReadWriteTool', 'idMenu', 'profile', 'idProfile', 'accessRight', 'idAccessProfile', 'list', 'accessProfileNoProjectSimple') ;
  	echo '</div><br/>';
  	$titlePane="habilitation_ReadWriteEnvironment";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('menuEnvironmentalParameter') . '">';
  	htmlDrawCrossTable('menuReadWriteEnvironment', 'idMenu', 'profile', 'idProfile', 'accessRight', 'idAccessProfile', 'list', 'accessProfileNoProjectSimple') ;
  	echo '</div><br/>';
  	$titlePane="habilitation_ReadWriteAutomation";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('menuAutomation') . '">';
  	htmlDrawCrossTable('menuReadWriteAutomation', 'idMenu', 'profile', 'idProfile', 'accessRight', 'idAccessProfile', 'list', 'accessProfileNoProjectSimple') ;
  	echo '</div><br/>';
  	$titlePane="habilitation_ReadWriteList";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('menuListOfValues') . '">';
  	htmlDrawCrossTable('menuReadWriteList', 'idMenu', 'profile', 'idProfile', 'accessRight', 'idAccessProfile', 'list', 'accessProfileNoProjectSimple') ;
  	echo '</div><br/>';
  	$titlePane="habilitation_ReadWriteType";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('menuType') . '">';
  	htmlDrawCrossTable('menuReadWriteType', 'idMenu', 'profile', 'idProfile', 'accessRight', 'idAccessProfile', 'list', 'accessProfileNoProjectSimple') ;
  	echo '</div><br/>';
  } else if ($type=='habilitationReport') {
  	htmlDrawCrossTable('report', 'idReport', 'profile', 'idProfile', 'habilitationReport', 'allowAccess', 'check', null, 'idReportCategory') ;
  } else if ($type=='habilitationOther') {
  	$titlePane="habilitationOther_Imputation";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionImputationDiary') . '">';
  	htmlDrawCrossTable(array('imputation'=>i18n('imputationAccess'), 
  	                         'workValid'=>i18n('workValidate'),
  	                         'diary'=>i18n('diaryAccess'),
  			                     'subscription'=>i18n('canSubscribeForOthers'),
  	                         'scheduledReport'=>i18n('autoSendReportAccess')), 
  	    'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'accessScopeSpecific') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_WorkCost";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionWorkCost') . '">';
  	htmlDrawCrossTable(array('work'=>i18n('workAccess'),'cost'=>i18n('costAccess')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'visibilityScope') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_AssignmentManagement";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionAssignmentManagement') . '">';
  	htmlDrawCrossTable(array('assignmentView'=>i18n('assignmentViewRight'),'assignmentEdit'=>i18n('assignmentEditRight')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_Buttons";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionButtons') . '">';
  	htmlDrawCrossTable(array('combo'=>i18n('comboDetailAccess'),'subtask'=>i18n('subTaskAccess'),'checklist'=>i18n('checklistAccess'),'joblist'=>i18n('joblistAccess'),'multipleUpdate'=>i18n('buttonMultiUpdate')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_ConditionalDisplay";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionConditionalDisplay') . '">';
  	htmlDrawCrossTable(array('votingPanelDetail'=>i18n('votingPanelDetail'),'nameVoterDetail'=>i18n('nameVoterDetail'),'simpleUI'=>i18n('simpleUI')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_PlanningRight";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionPlanningRight') . '">';
  	htmlDrawCrossTable(array('planning'=>i18n('planningRight'),'planningWithOveruse'=>i18n('canPlanWithInfiniteCapacity'),'resourcePlanning'=>i18n('resourcePlanningRight'),'changeValidatedData'=>i18n('changeValidatedData'),'changePriorityProj'=>i18n('changePriorityProject'),'changePriorityOther'=>i18n('changePriorityOther'),'changeManualProgress'=>i18n('changeManualProgress'),'validatePlanning'=>i18n('validatePlanning'),'enableAutomaticCal'=>i18n('enableAutomaticCal')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_Consolidation";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionConsolidation') . '">';
  	htmlDrawCrossTable(array('lockedImputation'=>i18n('buttonLockedImputation'),'validationImputation'=>i18n('buttonValidationImputation')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_Unlock";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionUnlock') . '">';
  	htmlDrawCrossTable(array('document'=>i18n('documentUnlockRight'),'requirement'=>i18n('requirementUnlockRight')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_Report";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionReport') . '">';
  	htmlDrawCrossTable(array('reportResourceAll'=>i18n('reportResourceAll'),'reportAdminProject'=>i18n('reportAdminProject')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_Financial";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('tabFinancial') . '">';
  	htmlDrawCrossTable(array(
  	    'generateProjExpense'=>i18n('generateProjectExpenseButton'),
  	    'situation'=>i18n('situationRight')),
  	    'scope', 'profile','idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
  	echo '</div><br/>';
  	$titlePane="habilitationOther_Delete";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('sectionDelete') . '">';
  	
  	if (Module::isModuleActive('moduleConfiguration')) {
      htmlDrawCrossTable(array(
      'canChangeNote'=>i18n('canChangeNote'),
      'canAddNoteClosedEl'=>i18n('canAddNoteClosedElement'),
      'canAddNoteReadOnlyEl'=>i18n('canAddNoteReadOnlyElement'),
      'canDeleteAttachment'=>i18n('canDeleteAttachment'),
      'canForceDelete'=>i18n('canForceDelete'),
      'canDeleteRealWork'=>i18n('canDeleteRealWork'),
      'canForceClose'=>i18n('canForceClose'),
      'canUpdateCreation'=>i18n('canUpdateCreationInfo'),
      'viewComponents'=>i18n('viewComponents'),
      'lockedLeftWork'=>i18n('lockedLeftWork'),
      'canWorkOnTicket'=>i18n('canWorkOnTicket'),
      'canWorkOnImputation'=>i18n('canWorkOnImputation'),
      'canManageVotes'=>i18n('canManageVotes'),
      'canAttributeLayout'=>i18n('canAttributeLayout'),
      'canCreateTags'=>i18n('canCreateTags'),
      ),
      'scope', 'profile','idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
    }else{
      htmlDrawCrossTable(array(
      'canChangeNote'=>i18n('canChangeNote'),
      'canAddNoteClosedEl'=>i18n('canAddNoteClosedElement'),
      'canAddNoteReadOnlyEl'=>i18n('canAddNoteReadOnlyElement'),
      'canDeleteAttachment'=>i18n('canDeleteAttachment'),
      'canForceDelete'=>i18n('canForceDelete'),
      'canDeleteRealWork'=>i18n('canDeleteRealWork'),
      'canForceClose'=>i18n('canForceClose'),
      'canUpdateCreation'=>i18n('canUpdateCreationInfo'),
      'viewComponents'=>i18n('viewComponents'),
      'lockedLeftWork'=>i18n('lockedLeftWork'),
      'canWorkOnTicket'=>i18n('canWorkOnTicket'),
      'canWorkOnImputation'=>i18n('canWorkOnImputation'),
      ),
      'scope', 'profile','idProfile', 'habilitationOther', 'rightAccess', 'list', 'listYesNo') ;
    }
  	
  	echo '</div><br/>';
  	$titlePane="habilitationOther_ResourceVisibility";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('resourceVisibility') . '">';
  	htmlDrawCrossTable(array('resVisibilityList'=>i18n('resourceVisibilityList'),'resVisibilityScreen'=>i18n('resourceVisibilityScreen')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'listTeamOrga') ;
  	echo '</div><br/>';
// ADD BY Marc TABARY - 2017-02-20 - ORGANIZATION VISIBILITY        
  	$titlePane="habilitationOther_OrganizationVisibility";
  	echo '<div dojoType="dijit.TitlePane" class="TitlePaneDisplay"';
  	echo ' open="' . ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true') . '"';
  	echo ' id="' . $titlePane . '" ';
  	echo ' onHide="saveCollapsed(\'' . $titlePane . '\');"';
  	echo ' onShow="saveExpanded(\'' . $titlePane . '\');"';
  	echo ' title="' . i18n('organizationVisibility') . '">';
  	htmlDrawCrossTable(array('orgaVisibilityList'=>i18n('organizationVisibilityList'),'orgaVisibilityScreen'=>i18n('organizationVisibilityScreen')), 'scope', 'profile', 'idProfile', 'habilitationOther', 'rightAccess', 'list', 'listOrgaSubOrga') ;
  	echo '</div><br/>';
// END ADD BY Marc TABARY - 2017-02-20 - ORGANIZATION VISIBILITY        
  } else {
  	drawTableFromObjectList($parameterList);
  }
  ?></form>
</div>
</div>
