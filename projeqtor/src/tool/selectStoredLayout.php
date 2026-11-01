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

/** ===========================================================================
 * Save a note : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */

require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/selectStoredLayout.php');
$user=getSessionUser();
$comboDetail=false;
if (pq_array_key_exists('comboDetail',$_REQUEST)) {
  $comboDetail=true;
}

if (! $comboDetail) {
  if (! $user->_arrayLayouts) {
    $user->_arrayLayouts=array();
  }
}
// Get the layout info
if (! pq_array_key_exists('idLayout',$_REQUEST)) {
  throwError('idLayout parameter not found in REQUEST');
}
$idLayout=$_REQUEST['idLayout'];
if (! pq_array_key_exists('layoutObjectClass',$_REQUEST)) {
  throwError('layoutObjectClass parameter not found in REQUEST');
}
$layoutObjectClass=$_REQUEST['layoutObjectClass'];

$layout=new Layout($idLayout);
$layoutArray=array("id"=>$layout->id,"comment"=>$layout->comment,"name"=>$layout->scope);

$user->_arrayLayouts[$layoutObjectClass]=$layoutArray;
$user->_arrayLayouts[$layoutObjectClass . "LayoutName"]=$layout->scope;
setSessionUser($user);
?>
<table width="100%" style="border: 1px solid grey;">
<tr>
  <td class='dialogLabel'>
    <label for="layoutNameDisplay" style="position:relative;top:5px;"><?php echo i18n("layoutName").'&nbsp;&nbsp;'?></label>
    <div type="text" dojoType="dijit.form.ValidationTextBox" name="layoutNameDisplay" id="layoutNameDisplay"
      style="width:520px;" trim="true" maxlength="100" class="input" value="<?php echo $layout->scope;?>">
  </td>
  <td style="text-align:center">
    <button title="<?php echo i18n('saveLayout')?>"   
     dojoType="dijit.form.Button"  
     id="dialogLayoutSave" name="dialogLayoutSave" class="resetMargin roundedButton notButton" style="height:24px;width:32px;margin-top:-1px;"
     iconClass="dijitButtonIcon dijitButtonIconSave imageColorNewGui" showLabel="false"> 
     <script type="dojo/connect" event="onClick" args="evt">saveLayout();</script>
    </button>
  </td>
</tr>
<tr>
  <td class='dialogLabel'>
    <label for="layoutComment" style="position:relative;top:5px;"><?php echo i18n("colComment").'&nbsp;&nbsp;'?></label>
    <textarea dojoType="dijit.form.Textarea" 
    id="layoutComment" name="layoutComment"
    style="width: 532px;height:100px;"
    maxlength="4000"
    class="input"><?php echo $layout->comment;?></textarea>   
  </td>
</tr>
</table>