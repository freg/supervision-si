<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
******************************************************************************
*** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
******************************************************************************
*
* Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
*
* This file is an add-on to ProjeQtOr, packaged as a plug-in module.
* It is NOT distributed under an open source license.
* It is distributed in a proprietary mode, only to the customer who bought
* corresponding licence.
* The company ProjeQtOr remains owner of all add-ons it delivers.
* Any change to an add-ons without the explicit agreement of the company
* ProjeQtOr is prohibited.
* The diffusion (or any kind if distribution) of an add-on is prohibited.
* Violators will be prosecuted.
*
*** DO NOT REMOVE THIS NOTICE ************************************************/

function kanbanAddPrinc($line) {
  global $typeKanbanC;
	$addInPrinc = '';
	if ($line ['idstatus']) {
	    $isCopyStatus = SqlList::getFieldFromId('Status', $line['idstatus'], 'isCopyStatus');
	    $color = SqlList::getFieldFromId ( "Status", $line ['idstatus'], 'color' );
	    $addInPrinc .= '<table><tr>';
		$addInPrinc .= '<td><div style="padding:'.((pq_strtolower($color) == "#ffffff")?'3px 5px 4px 5px':'5px').';width: 75px;text-align: center;" >'.formatColorRounded ($color, 15  , 8, 'left', null, SqlList::getNameFromId ( "Status", $line ['idstatus'] ), 7).'</div></td>';
		if($isCopyStatus){
		  $ws=new WorkflowStatus();
		  $profile = getSessionUser()->getProfile();
		  $crit=array('idWorkflow'=>'0', 'allowed'=>1, 'idProfile'=>$profile, 'idStatusFrom'=>'1');
		  $wsList=$ws->getSqlElementsFromCriteria($crit, false);
		  if(count($wsList)>0){
		    $next=$wsList[0]->id;
		    $addInPrinc .= '<td><div style="cursor:pointer;" title="'.i18n("moveStatusTo", array(SqlList::getNameFromId('Status', $next))).'" onclick="sendChangeKanBan('.$line ['id'].',\'Status\','.$next.',null,'.$line['idstatus'].');">';
		    $addInPrinc .= '<img src="css/customIcons/new/iconMoveTo.svg" class="imageColorNewGui" style="width:16px;height:16px"/>';
		    $addInPrinc .= '</div></td>';
		  }
		}
		$addInPrinc .= '</tr></table>';
	}
	return $addInPrinc;
}

function kanbanAddProjectName($line) {
  $kanbanFullWidthElement = Parameter::getUserParameter ( "kanbanFullWidthElement" );
  $addProjectName = '';
  if ($line['idproject'] and $kanbanFullWidthElement == "on"){
    $addProjectName .= '<table><tr>';
    $projectName = SqlList::getNameFromId('Project',$line ['idproject']);
    $addProjectName .= '<td style="display:flex;gap:5px;"><span class="imageColorNewGuiNoSelection"><div class="iconProject iconSize16"></div></span>
        <div style="font-size: 12px;">'.$projectName.'</div></td>';
    $addProjectName .= '</tr></table>';
  }
  return $addProjectName;
}

function kanbanAddProduct($line) {
  $addInProduct = '';
  $kanbanFullWidthElement = Parameter::getUserParameter ( "kanbanFullWidthElement" );
  if ($kanbanFullWidthElement == "on") {
    if ($line ['idtargetproductversion']) {
      if (isset($line['name5'])) $versionName=$line['name5'];
      else $versionName = SqlList::getNameFromId ( "TargetProductVersion", $line ['idtargetproductversion'] );
      if ($versionName == $line ['idtargetproductversion']) {
        $versionName = SqlList::getNameFromId ( "ProductVersion", $line ['idtargetproductversion'] );
      }
      $addInProduct .= '
    	<div style="float:left;width:100%;padding: 0px 0px 5px 5px;" class="kanbanVersion">
			  <div title="'.i18n('colIdTargetProductVersion').'" class="imageColorNewGuiNoSelection iconProductVersion16 iconProductVersion iconSize16" style="margin-top:5px;float:left"></div>
        <div title="'.$versionName.'" id="targetProductVersion' . $line ['id'] . '" style="float:left;margin:5px 0 0 2px;overflow:hidden;color:var(--color-medium);">
          ' . $versionName . '
        </div>
      </div>';
    }
  } else {
    if ($line ['idtargetproductversion']) {
      if (isset($line['name5'])) $versionName=$line['name5'];
      else $versionName = SqlList::getNameFromId ( "TargetProductVersion", $line ['idtargetproductversion'] );
      if ($versionName == $line ['idtargetproductversion']) {
        $versionName = SqlList::getNameFromId ( "ProductVersion", $line ['idtargetproductversion'] );
      }
      $addInProduct .= '<div style="padding:0px 10px 0px 5px;overflow:hidden;white-space:nowrap;">
      <table style="margin: 2px;">
        <tr>
          <td title="'.i18n('colIdTargetProductVersion').'">
            <div class="imageColorNewGuiNoSelection iconProductVersion16 iconProductVersion iconSize16" style="width:16px;height:16px;float:left"></div>
          </td>
          <td title="'.$versionName.'" id="targetProductVersion' . $line ['id'] . '"  style="float:left;overflow:hidden;margin-left:2px;color:var(--color-medium);">
            ' . $versionName . '
          </td>
        </tr>
      </table></div>';
    }
  }
  return $addInProduct;
}

function kanbanAddActivityPlanning($line) {
  $addInProduct = '';
  $kanbanFullWidthElement = Parameter::getUserParameter ( "kanbanFullWidthElement" );
  if ($kanbanFullWidthElement == "on") {
    if (isset ($line['idactivity']) and $line['idactivity'] != 0) {
      $addInProduct .= '
      <div style="float:left;width:100%;padding: 0px 0px 5px 5px;" class="kanbanVersion">
        <div title="'.((isset($line['WorkElement']))?i18n('colPlanningActivity'):i18n('colParentActivity')).'" class="imageColorNewGuiNoSelection iconActivity16 iconActivity iconSize16" style="margin-top:5px;float:left"></div>
        <div title="'.SqlList::getNameFromId ( "Activity", $line ['idactivity'] ).'"class="kanbanActivity" style="margin:5px 0 0 2px;overflow:hidden;float:left;color:var(--color-medium);">
          ' . SqlList::getNameFromId ( "Activity", $line ['idactivity'] ) . '
        </div>
      </div>';
    }
  } else {
    if (isset ( $line ['idactivity'] ) and $line ['idactivity']!= 0) {
      $addInProduct .= '<div style="padding:0px 10px 0px 5px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;">
      <table style="margin: 2px;">
        <tr>
          <td title="'.((isset($line['WorkElement']))?i18n('colPlanningActivity'):i18n('colParentActivity')).'">
            <div class="imageColorNewGuiNoSelection iconActivity16 iconActivity iconSize16" style="width:16px;height:16px;float:left"></div>
          </td>
          <td title="'.SqlList::getNameFromId ( "Activity", $line ['idactivity'] ).'" style="float:left;overflow:hidden;margin-left:2px;color:var(--color-medium);">
            ' . SqlList::getNameFromId ( "Activity", $line ['idactivity'] ) . '
          </td>
        </tr>
      </table></div>';
    }
  }
  return $addInProduct;
}

function kanbanAddDescr($line, $type) {
	$addInDescr = '';
	$kanbanFullWidthElement = Parameter::getUserParameter ( "kanbanFullWidthElement" );

	$destWidth=RequestHandler::getValue('destinationWidth');
	if (!$destWidth) $destWidth=1920;
	$nbCol=(isset($jsonDecode['column']) and is_array($jsonDecode['column']))?count($jsonDecode['column']):1;
	$spaces=10*($nbCol+1);
	$ticketWidth=(($destWidth-$spaces)/$nbCol)-40;
	if ($ticketWidth<305) $ticketWidth=305;
	$nbTktPerCol=intval($ticketWidth/150);
	$ticketWidthSmall=(round($ticketWidth/$nbTktPerCol,1)-(2*$nbTktPerCol)+3).'px';
	$ticketRelativeWidth=($kanbanFullWidthElement == "on")?$ticketWidth:(round($ticketWidth/$nbTktPerCol,1)-(2*$nbTktPerCol)+3);
	
	if (isset ( $line ['description'] )) {
		$description=$line ['description'];
        $minChar = 200;
        if(pq_strpos($description, '<img ') != ''){
          $minChar = 400;
          $description=pq_str_replace('<img ','<img style="max-width:'.($ticketRelativeWidth-10).'px;" onClick="showImage(\'Note\',this.src,\' \');"',$description);
          $img = pq_substr($description, pq_strpos($description, '<img '), (pq_strpos($description, '/>')-pq_strpos($description, '<img '))+2);
          $description = pq_substr($description, 0, pq_strpos($description, '<img ')).'<div>#IMGREPLACED#</div>'.pq_substr($description, pq_strpos($description, '<img '));
          $text = new Html2Text ($description);
          $descr = $text->getText ();
          $descr=pq_htmlspecialchars($descr);
          $descr=pq_str_replace('#IMGREPLACED#',$img,$descr);
        }else{
          $text = new Html2Text ($description);
          $descr = $text->getText ();
          $descr=pq_htmlspecialchars($descr);
        }
		if (pq_strlen ($description) > 4000) {
      	    $descr1 = pq_substr ( $descr, 0, 4000);
      		$ticketDescr = nl2brForPlainText ( $descr1 );
      		$descr2 = pq_substr ( $descr, 0, $minChar );
      		$ticketDescr2 = nl2brForPlainText ( $descr2 );
		} else {
  	      $ticketDescr=$description;
          $descr2 = pq_substr ( $descr, 0, $minChar);
          $ticketDescr2 = nl2brForPlainText ( $descr2 );
		}
		if($line['description'] == ''){
		  $ticketDescr = '<div style="font-style:italic; color:#CDCADB; ">' . i18n ( "kanbanNoDescription" ) . '</div>';
		  $ticketDescr2 = '<div style="font-style:italic; color:#CDCADB; ">' . i18n ( "kanbanNoDescription" ) . '</div>';
		}
    	if ($kanbanFullWidthElement == "on") {
    		return $ticketDescr;
    	} else {
  			return $ticketDescr2;
  		}
    }
}

function displayAllWork($line, $type = 0, $numberLetter = 2) {
	global $typeKanbanC;
	$seeWork = Parameter::getUserParameter ( "kanbanSeeWork" . Parameter::getUserParameter ( "kanbanIdKanban" ) );
	$seeWork=($seeWork=='on' or $seeWork=='1')?true:false;
	if ($seeWork && PlanningElement::getWorkVisibility ( getSessionUser ()->idProfile ) == "ALL") {
		$seeWork = true;
	} else {
		$seeWork = false;
	}
	if (! $seeWork) {
		return '';
	}
	if (! isset ( $line ['plannedWork'] )) {
		$line ['plannedWork'] = 0;
	}
	if (! isset ( $line ['realWork'] )) {
		$line ['realWork'] = 0;
	}
	if (! isset ( $line ['leftWork'] )) {
		$line ['leftWork'] = 0;
	}
	if (! isset ( $line ['assignedWork'] )) {
		$line ['assignedWork'] = 0;
	}
	$formatter = 'workFormatter';
	if ($typeKanbanC == 'Ticket')
		$formatter = 'kanbanImputationFormatter';
	if ($type == 0) {
	  if($line['id'] != "n"){
      $id = $line['id'];
      $pe = new PlanningElement();
      $crit = array('refId'=>$id,'refType'=>"Activity");
      
      $peLst = $pe->getSqlElementsFromCriteria($crit,false);
      foreach ($peLst as $test){
        $assW = $test->assignedWork;
        $realW = $test->realWork;
        $leftW = $test->leftWork;
      }
      $idKanban = (Parameter::getUserParameter ( "kanbanIdKanban" ));
      $kanban = new Kanban($idKanban);
        
      if ($typeKanbanC == 'Ticket' && $kanban->type == 'Activity') {
        echo '
          <div style="margin-top:2px;"><table style="float:left;margin-right:10px;margin-top:5px;">
            <tr>
              <td class="linkHeader" style="padding:3px;cursor:auto;min-width:40px">' . i18n ( 'colAssigned' ) . '</td>
                <td class="linkHeader" style="padding:3px;cursor:auto;min-width:40px">' . i18n ( 'colReal' ) . '</td>
                <td class="linkHeader" style="padding:3px;cursor:auto;min-width:40px">' . i18n ( 'colLeft' ) . '</td>
              </tr>
              <tr>
                <td id="assignedWorkA' . $id . '" valueWork="' . pq_str_replace ( ',', '.', $assW != null ? $assW : 0 ) . '" class="linkData" WorkFormat="' . Work::displayShortWorkUnit () . '" style="padding:3px;cursor:auto;text-align:center;">' . $formatter ( $assW ) . '</td>
                <td id="realWorkA' . $id . '" valueWork="' . pq_str_replace ( ',', '.', $realW != null ? $realW : 0 ) . '" class="linkData" WorkFormat="' . Work::displayShortWorkUnit () . '" style="padding:3px;cursor:auto;text-align:center;">' . $formatter ( $realW ) . '</td>
                <td id="leftWorkA' . $id . '" valueWork="' . pq_str_replace ( ',', '.', $leftW != null ? $leftW : 0 ) . '" class="linkData" WorkFormat="' . Work::displayShortWorkUnit () . '" style="padding:3px;cursor:auto;text-align:center;">' . $formatter ( $leftW ) . '</td>
              </tr>
            </table>';
      }else {
        echo '<div style="">';
      }
    }else {
      echo '<div style="margin-top:6px;">';
    }
		return '
      <table style="float:right;margin-top:5px;">
        <tr>
          <td class="linkHeader" style="padding:3px;cursor:auto;min-width:40px">' . i18n ( 'colEstimated' ) . '</td>
          <td class="linkHeader" style="padding:3px;cursor:auto;min-width:40px">' . i18n ( 'colReal' ) . '</td>
          <td class="linkHeader" style="padding:3px;cursor:auto;min-width:40px">' . i18n ( 'colLeft' ) . '</td>
        </tr>
        <tr>
          <td id="plannedWorkC' . $line ['id'] . '" valueWork="' . pq_str_replace ( ',', '.', $line ['plannedWork'] != null ? $line ['plannedWork'] : 0 ) . '" class="linkData" WorkFormat="' . Work::displayShortWorkUnit () . '" style="padding:3px;cursor:auto;text-align:center;">' . $formatter ( $line ['plannedWork'] ) . '</td>
          <td id="realWorkC' . $line ['id'] . '" valueWork="' . pq_str_replace ( ',', '.', $line ['realWork'] != null ? $line ['realWork'] : 0 ) . '" class="linkData" WorkFormat="' . Work::displayShortWorkUnit () . '" style="padding:3px;cursor:auto;text-align:center;">' . $formatter ( $line ['realWork'] ) . '</td>
          <td id="leftWorkC' . $line ['id'] . '" valueWork="' . pq_str_replace ( ',', '.', $line ['leftWork'] != null ? $line ['leftWork'] : 0 ) . '" class="linkData" WorkFormat="' . Work::displayShortWorkUnit () . '" style="padding:3px;cursor:auto;text-align:center;">' . $formatter ( $line ['leftWork'] ) . '</td>
        </tr>
        <tr>
          <td>
          </td>
        </tr>
      </table>
    </div>';
	}
	if ($type == 1) {
	  if (isNewGui()) return '
       <table style="background-color:#eeeeee;cursor:move;width:100%;">
         <tr>
           <td id="plannedWork' . $line ['id'] . '" 
               valueWork="' . pq_str_replace ( ',', '.', $line ['plannedwork'] != null ? $line ['plannedwork'] : 0 ) . '" 
               class="" title="' . i18n ( 'colEstimated' ) . '" style="width:33%;text-align:center;padding:0px 3px 3px 3px;font-size:80%;">
               <span style="font-size:90%;color:var(--color-medium);">'.i18n ( 'colEstimated' ).'</span><br/>' . $formatter ( $line ['plannedwork'] ) . '</td>
           <td id="realWork' . $line ['id'] . '" 
               valueWork="' . pq_str_replace ( ',', '.', $line ['realwork'] != null ? $line ['realwork'] : 0 ) . '" 
               class="" title="' . i18n ( 'colReal' ) . '" style="width:33%;text-align:center;padding:0px 3px 3px 3px;font-size:80%;">
               <span style="font-size:90%;color:var(--color-medium);">'.i18n ( 'colReal' ).'</span><br/>' . $formatter ( $line ['realwork'] ) . '</td>
           <td id="leftWork' . $line ['id'] . '" 
               valueWork="' . pq_str_replace ( ',', '.', $line ['leftwork'] != null ? $line ['leftwork'] : 0 ) . '" 
               class="" title="' . i18n ( 'colLeft' ) . '" style="width:33%;text-align:center;padding:0px 3px 3px 3px;font-size:80%;">
               <span style="font-size:90%;color:var(--color-medium);">'.i18n ( 'colLeft' ).'</span><br/>' . $formatter ( $line ['leftwork'] ) . '</td>
         </tr>
       </table>'; 
	    
		else return '
       <table style="background-color:#eeeeee;cursor:move;width:100%;">
         <tr>
           <td id="plannedWork' . $line ['id'] . '" valueWork="' . pq_str_replace ( ',', '.', $line ['plannedwork'] != null ? $line ['plannedwork'] : 0 ) . '" class="linkData" title="' . i18n ( 'colEstimated' ) . '" style="text-align:center;padding:3px;">' . $formatter ( $line ['plannedwork'] ) . '</td>
           <td id="realWork' . $line ['id'] . '" valueWork="' . pq_str_replace ( ',', '.', $line ['realwork'] != null ? $line ['realwork'] : 0 ) . '" class="linkData" title="' . i18n ( 'colReal' ) . '" style="text-align:center;padding:3px;">' . $formatter ( $line ['realwork'] ) . '</td>
           <td id="leftWork' . $line ['id'] . '" valueWork="' . pq_str_replace ( ',', '.', $line ['leftwork'] != null ? $line ['leftwork'] : 0 ) . '" class="linkData" title="' . i18n ( 'colLeft' ) . '" style="text-align:center;padding:3px;">' . $formatter ( $line ['leftwork'] ) . '</td>
         </tr>
       </table>';
	}
	return '';
}
function kanbanImputationFormatter($value) { // This function for V5.5.2 compatibility, as equivalent does not exist yet in GeneralWork class
	return Work::displayImputation ( $value ) . ' ' . Work::displayShortImputationUnit ();
}
?>