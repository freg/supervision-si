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
require_once "../tool/projeqtor.php";

$objectClass = RequestHandler::getField('refType');
$objectId = RequestHandler::getId('refId');
$idResource = RequestHandler::getId('idResource');
$curDate = RequestHandler::getDatetime('curDate');
$idAssignment = RequestHandler::getId('idAssignment');
$idProject = RequestHandler::getId('idProject');
$idWorkValue = RequestHandler::getValue('idWorkValue');
$workOldValue = RequestHandler::getValue('workOldValue');
$readonlyDispatchWorkDetail = RequestHandler::getBoolean('readonlyDispatchWorkDetail');

$obj=new $objectClass($objectId); 
$crit=array('refType'=>$objectClass,'refId'=>$objectId);
$we=SqlElement::getSingleSqlElementFromCriteria('WorkElement', $crit);
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();

$crit = array('refType'=>$objectClass,'refId'=>$objectId, 'workDate'=>$curDate, 'idResource'=>$idResource);
$work = SqlElement::getSingleSqlElementFromCriteria('Work', $crit);

$arrayWorkDetail=array();

$workDetail = new WorkDetail();
$critForWorkDetail = array('idWork'=>$work->id);
$listWorkDetail = $workDetail->getSqlElementsFromCriteria($critForWorkDetail);
$arrayKey=array();
foreach ($listWorkDetail as $wD){
  $key = $wD->id;
  $arrayKey[$wD->id] = $wD->id;
  if (!isset($arrayWork[$key])){
    $arrayWorkDetail[$key]=array('id'=>$wD->id, 'idWorkCategory'=>$wD->idWorkCategory, 'work'=>$wD->work, 'uncertainties'=>$wD->uncertainties,'progress'=>$wD->progress);
  }
}
if (! $readonlyDispatchWorkDetail){
  while (count($arrayWorkDetail) < 2) {
    $arrayWorkDetail[] = array('id' => '', 'idWorkCategory' => ' ' ,'work' => '', 'uncertainties' => '', 'progress' => '');
  }
}

ksort($arrayWorkDetail);

?>
<form dojoType="dijit.form.Form" id="dialogDispatchWorkImputationForm" name="dialogDispatchWorkImputationForm" action="">
  <table style="width: 100%; border-collapse: collapse;">
    <?php if (count($arrayWorkDetail) !=0 || (!$readonlyDispatchWorkDetail && count($arrayWorkDetail) == 0)){ ?>
    <thead>
      <tr>
        <td style="text-align: right; font-weight: bold; visibility: hidden;"><?php echo i18n("sum");?></td>
        <td>&nbsp;</td>
        <td style="text-align: center; font-weight: bold; padding: 5px;" colspan="2"><?php echo ucfirst(i18n('colWork'));?></td>
        <td>&nbsp;</td>
        <td style="text-align: center; font-weight: bold; padding: 5px;" colspan="2"><?php echo i18n('colWorks');?></td>
        <td>&nbsp;</td>
        <td style="text-align: center; font-weight: bold; padding: 5px;" colspan="2"><?php echo i18n('colUncertainties');?></td>
        <td>&nbsp;</td>
        <td style="text-align: center; font-weight: bold; padding: 5px;" colspan="2"><?php echo i18n('colProgressImputation');?></td>
        <td>&nbsp;</td>
      </tr>
    </thead>
    <?php }else{?>
    <td> <?php echo i18n('noWorkDetailThisDayThisAcitvity');?></td>
    <?php }?>
    <tbody id="dialogDispatchImputationTable">
<input type="hidden" name="curDate" value="<?php echo $curDate;?>" />
<input type="hidden" name="idAssignment" value="<?php echo $idAssignment;?>" />
<input type="hidden" name="idResource" value="<?php echo  $idResource;?>"/>
<input type="hidden" name="refType" value="<?php echo $objectClass;?>" />
<input type="hidden" name="refId" value="<?php echo $objectId;?>" />
<input type="hidden" name="idProject" value="<?php echo $idProject;?>" />
<input type="hidden" id="inputWorkValue" name="inputWorkValue" value="<?php echo 'workValue'.$idWorkValue;?>" />

<?php
$cpt = 0;
foreach($arrayWorkDetail as $key=>$workD) {
  $cpt++;
?> 
<input type="hidden" name="idWorkForWorkDetail" value="<?php echo $work->id;?>" />
<input type="hidden" name="idWorkDetail" value="<?php echo implode(',',$arrayKey);?>" />
        <tr>
          <!-- Work -->
          <td style="text-align: right; font-weight: bold; visibility: hidden;"><?php echo i18n("sum");?></td>
          <td>&nbsp;&nbsp;</td>
          <td style="text-align: center; padding: 5px; width: 52px;vertical-align: top;">
            <div dojoType="dijit.form.NumberTextBox" style="width: 50px; margin: 0 auto; display: block;" 
              value="<?php if ($cpt == 1 && $workD['work'] == '' ) echo $workOldValue;
                           else if  (isset($workD['work']) && $workD['work'] !== '' ) echo Work::displayImputation($workD['work']);
                           else echo '0';?>" 
              onchange="updateDispatchWorkImputationTotal('dispatchWorkImputationValue_','dispatchWorkImputationTotal');
                        toggleSelectState('dispatchWorkImputationValue_<?php echo $cpt;?>',
                                          'dispatchWorkImputation_<?php echo $cpt;?>',
                                          'uncertaintiesDispatchWorkImputation_<?php echo $cpt;?>',
                                          'progressDispatchWorkImputation_<?php echo $cpt;?>');"
              name="dispatchWorkImputationValue[]" id="dispatchWorkImputationValue_<?php echo $cpt;?>"
              <?php  if ($readonlyDispatchWorkDetail) echo 'readOnly="true"';?>>
              <?php echo $keyDownEventScript; ?>
            </div>
          </td>
          <td style="text-align: left; padding: 5px; width: 1px;vertical-align: top;line-height: 30px;"><?php echo Work::displayShortImputationUnit();?></td>
          <td>&nbsp;</td>
          
          <!-- Work Imputation -->
          <td colspan="2" style="text-align: center; padding: 5px;vertical-align: top;">
            <select dojoType="dijit.form.FilteringSelect" style="width: 150px; margin: 0 auto; display: block;" 
              id="dispatchWorkImputation_<?php echo $cpt;?>" name="dispatchWorkImputation[]" <?php echo autoOpenFilteringSelect();?>
              onMouseDown="dijit.byId(this.id).toggleDropDown();" value="<?php echo $workD['idWorkCategory']?>" 
              <?php  if ($readonlyDispatchWorkDetail) echo 'readOnly="true"';
                     elseif ($cpt == 1 && $workOldValue != 0) echo 'readOnly="false"';
                     elseif ( $workD['work'] != '') echo 'readOnly="false"';
                     else echo 'readOnly="true"'; ?> selectOnClick="true">
              <?php htmlDrawOptionForReference('idWorkCategory', null, $obj, false, array('refId', 'refType'), array($objectId, $objectClass)); ?>
            </select>
          </td>
          <?php if (!$readonlyDispatchWorkDetail){?>
          <td style="text-align: center; padding: 8px 5px 5px 5px;vertical-align: top;line-height: 30px;" class="imageColorNewGui" id="addWorkImputationLine" 
              name="addWorkImputationLine" onclick="addWorkImputationLine('<?php echo $objectClass; ?>' , '<?php echo $objectId;?>' , <?php echo $cpt;?>);" 
              title="<?php echo i18n('addWorkImputation');?>">
            <?php echo formatMediumButton('Add');?>
          </td>
          <?php }else {?>
          <td>
          </td>
          <?php }?>
          <td>&nbsp;</td>
  
          <!-- Uncertainties -->
          <td style="text-align: center; padding: 0 2px 7px 0;">
            <textarea id="uncertaintiesDispatchWorkImputation_<?php echo $cpt;?>" name="uncertaintiesDispatchWorkImputation[]" value="<?php echo $workD['uncertainties']?>" 
              <?php  if ($readonlyDispatchWorkDetail) echo 'readOnly="true"';
                     elseif ($cpt == 1 && $workOldValue != 0) echo 'readOnly="false"';
                     elseif ( $workD['work'] != '') echo 'readOnly="false"';
                     else echo 'readOnly="true"'; ?>
              maxlength="4000" style="width: 250px; height: 50px; margin: 0 auto; display: block;" 
              dojoType="dijit.form.SimpleTextarea"></textarea
          </td>
          <td>&nbsp;</td>
  
          <!-- Progress Imputation -->
          <td style="text-align: center;padding: 0 2px 7px 0;">
            <textarea id="progressDispatchWorkImputation_<?php echo $cpt;?>" name="progressDispatchWorkImputation[]" value="<?php echo $workD['progress']?>" 
              <?php  if ($readonlyDispatchWorkDetail) echo 'readOnly="true"';
                     elseif ($cpt == 1 && $workOldValue != 0) echo 'readOnly="false"';
                     elseif ( $workD['work'] != '') echo 'readOnly="false"';
                     else echo 'readOnly="true"'; ?>
              maxlength="4000" style="width: 250px; height: 50px; margin: 0 auto; display: block;" 
              dojoType="dijit.form.SimpleTextarea"></textarea>
          </td>
        </tr>
<?php 
}
?>
      </tbody>
    </table>    
  <table>
  <?php if (count($arrayWorkDetail) != 0 || (!$readonlyDispatchWorkDetail && count($arrayWorkDetail) == 0)){?>
    <tr>
      <td style="text-align: right; font-weight: bold;"><?php echo i18n("sum");?></td>
      <td>&nbsp;&nbsp;</td>
      <td style="text-align: center; padding: 5px; width: 52px;">
        <div dojoType="dijit.form.NumberTextBox" style="width: 50px; margin: 0 auto; display: block;" 
          value=<?php echo $workOldValue?> readonly="true" disabled="true"
          name="dispatchWorkImputationTotal" id="dispatchWorkImputationTotal">
        </div>
      </td>
      <td style="text-align: left; padding: 5px; width: 1px;"><?php echo Work::displayShortImputationUnit();?></td>
    </tr>
  </table>
  <?php }?>
  <?php if ( !$readonlyDispatchWorkDetail){?>
  <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px;">
    <div style="text-align: left;"></div>
    <div style="text-align: center;">
      <button dojoType="dijit.form.Button" type="button" 
        onclick="dijit.byId('dialogDispatchWorkImputation').hide();" 
        style="font-size: 14px;" class="mediumTextButton">
        <?php echo i18n("buttonCancel");?>
      </button>
      <button id="dialogDispatchWorkSubmit" dojoType="dijit.form.Button" type="submit" 
        style="font-size: 14px;" class="mediumTextButton"
        onclick="this.focus();protectDblClick(this);saveWorkDetailImputation(<?php echo $cpt?>,'<?php echo 'colId_' . $curDate; ?>',<?php echo 'workOldValue'.$idWorkValue?>);return false;">
        <?php echo i18n("buttonOK");?>
      </button>
    </div>
    <div>
      <div class="" id="addDispatchWorkImputationLine" 
           onclick="addDispatchWorkImputationLine('<?php echo Work::displayShortWorkUnit();?>', '<?php echo $objectClass; ?>' , '<?php echo $objectId;?>');" title="<?php echo i18n('addLine');?>" 
           style="cursor: pointer; font-size: 14px; width: 22px; padding-right:15px;">
        <?php echo formatMediumButton('Add');?>
      </div>
    </div>
    <?php }?>
  </div>
</form>

