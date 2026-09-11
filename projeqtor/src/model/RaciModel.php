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

require_once('_securityCheck.php');
class RaciModel extends SqlElement {

  public $_sec_Description;
  public $id;
  public $name;
  public $sortOrder=0;
  public $idle;
  public $_sec_RaciMatrix;
  public $_spe_raciMatrix;
  public $_raciMatrix_colSpan="2";

  private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%"># ${id}</th>
    <th field="name" width="80%">${name}</th>
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';
  private static $_fieldsAttributes=array(
      "sortOrder"=>"hidden"
      );

  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

  function __destruct() {
    parent::__destruct();
  }

  protected function getStaticFieldsAttributes() {
  	return self::$_fieldsAttributes;
  }

  protected function getStaticLayout() {
    return self::$_layout;
  }

  public function control() {
  	$result="";
  	if (pq_array_key_exists('raciMatrixSubmitted', $_REQUEST)) {
  	  $raciControl=$this->controlRaciMatrixFromRequest();
  	  if ($raciControl!='OK') $result.=$raciControl;
  	}
  	$defaultControl=parent::control();
  	if ($defaultControl!='OK') {
  	  $result.=$defaultControl;
  	}
  	if ($result=="") {
  	  $result='OK';
  	}
  	return $result;
  }

  public function drawSpecificItem($item){
  	if ($item=='raciMatrix') {
  	  $canUpdate=(securityGetAccessRightYesNo('menuRaciModel', 'update', $this)=="YES");
  	  return $this->drawMatrix($canUpdate, null);
  	}
  	return "";
  }

  public static function getValueColor($value) {
  	switch ($value) {
  	  case 'R': return '#C6E0B4';
  	  case 'A': return '#FFE699';
  	  case 'C': return '#BDD7EE';
  	  case 'I': return '#F8CBAD';
  	}
  	return '';
  }

  private static function getValueLabel($value) {
  	switch ($value) {
  	  case 'R': return i18n('raciResponsible');
  	  case 'A': return i18n('raciAccountable');
  	  case 'C': return i18n('raciConsulted');
  	  case 'I': return i18n('raciInformed');
  	}
  	return '';
  }

  private static function drawRaciBadge($value, $backgroundColor=null, $withShadow=false) {
  	if (! $value) return '';
  	$style='display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;font-weight:bold;font-size:15px;';
  	$style.=($backgroundColor)?'background-color:'.$backgroundColor.';color:#ffffff;':'background-color:#ffffff;color:#303044;';
  	if ($withShadow) $style.='text-shadow:#000000 1px 1px 2px;';
  	return '<span title="'.htmlEncode(self::getValueLabel($value)).'" style="'.$style.'">'.htmlEncode($value).'</span>';
  }

  private function drawRaciLegend($projectDisplay=false) {
  	$result='<div style="display:flex;align-items:center;gap:25px;flex-wrap:wrap;margin:15px 0;padding:10px 0;width:max-content;max-width:100%;box-sizing:border-box;">';
  	foreach (array('R','A','C','I') as $value) {
  	  $result.='<span style="display:inline-flex;align-items:center;gap:8px;white-space:nowrap;">';
  	  $result.=self::drawRaciBadge($value, self::getValueColor($value), true);
  	  $result.='<span>'.self::getValueLabel($value).'</span>';
  	  $result.='</span>';
  	}
  	$result.='</div>';
  	return $result;
  }

  public function drawMatrix($canUpdate=false, $idProject=null) {
  	global $print;
  	$result="";
  	if (! $this->id) {
  	  return '<i>'.i18n('raciSaveModelFirst').'</i>';
  	}
  	$editable=($canUpdate and ! $idProject and ! $print and $this->idle!=1);

  	$fnc=new RaciFunction();
  	$functions=$fnc->getSqlElementsFromCriteria(array('idRaciModel'=>$this->id), false, null, 'sortOrder asc, name asc');
  	$rl=new RaciRole();
  	$roles=$rl->getSqlElementsFromCriteria(array('idRaciModel'=>$this->id), false, null, 'sortOrder asc, name asc');
  	$cl=new RaciCell();
  	$cells=$cl->getSqlElementsFromCriteria(array('idRaciModel'=>$this->id));
  	$cellMap=array();
  	foreach ($cells as $cell) {
  	  $cellMap[$cell->idRaciFunction][$cell->idRaciRole]=$cell->value;
  	}
  	$nbRoles=count($roles);

  	if ($editable) {
  	  $result.='<input type="hidden" id="raciMatrixSubmitted" name="raciMatrixSubmitted" value="1" />';
  	}

  	if ($idProject) {
  	  $result.='<input type="hidden" id="raciModelId" value="'.htmlEncode($this->id).'" />';
  	  $result.='<input type="hidden" id="raciProjectId" value="'.htmlEncode($idProject).'" />';
  	  $dropResourceHere=str_replace('"', '\"', htmlEncode(i18n('raciDropResourceHere')));
  	  $result.='<style>.raciRoleDndSource.raciDndEmpty:before{content:"'.$dropResourceHere.'";display:block;font-style:italic;color:#777777;padding:5px;text-align:center;}</style>';
  	}

  	$result.=$this->drawRaciLegend(($idProject)?true:false);

  	if ($idProject) {
  	  $result.='<div style="display:flex;align-items:flex-start;gap:15px;flex-wrap:wrap;">';
  	  $result.='<div style="flex:0 1 auto;max-width:100%;overflow:auto;">';
  	}
  	$result.='<table id="raciMatrixTable" class="table" style="width:auto;border-collapse:collapse;" data-model-id="'.htmlEncode($this->id).'">';
  	$result.='<thead><tr>';
  	$result.='<td class="assignHeader" rowspan="2" style="width:200px;min-width:200px;max-width:200px;vertical-align:middle;padding:3px 4px;">';
  	$result.='<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;">';
  	$result.='<b>'.i18n('raciFunctionColumn').'</b>';
  	if ($editable) {
  	  $result.='<div style="display:flex;align-items:center;justify-content:center;gap:6px;">';
  	  $result.='<a onClick="addRaciFunctionLine(1);" title="'.i18n('raciAddFunction').'">'.formatSmallButton('Add').'</a>';
  	  $result.='<a onClick="addRaciFunctionLine(5);" title="'.i18n('raciAddFunction').' x5">'.formatSmallButton('NewMultiple').'</a>';
  	  $result.='</div>';
  	}
  	$result.='</div>';
  	$result.='</td>';
  	$result.='<td id="raciRoleColumnTitle" class="assignHeader" colspan="'.(($nbRoles>0)?$nbRoles:1).'" style="text-align:center;padding:3px 4px;">';
  	$result.='<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;">';
  	$result.='<b>'.i18n('raciRoleColumn').'</b>';
  	if ($editable) {
  	  $result.='<div style="display:flex;align-items:center;justify-content:center;gap:6px;">';
  	  $result.='<a onClick="addRaciRoleColumn(1);" title="'.i18n('raciAddRole').'">'.formatSmallButton('Add').'</a>';
  	  $result.='<a onClick="addRaciRoleColumn(5);" title="'.i18n('raciAddRole').' x5">'.formatSmallButton('NewMultiple').'</a>';
  	  $result.='</div>';
  	}
  	$result.='</div>';
  	$result.='</td>';
  	$result.='</tr><tr id="raciRoleHeaderRow">';
  	if ($nbRoles>0) {
  	  foreach ($roles as $role) {
  	    $result.=$this->drawRaciRoleHeaderCell($role, $editable, ($idProject)?true:false);
  	  }
  	} else {
  	  $result.='<td id="raciNoRoleHeaderCell" class="assignHeader" style="width:200px;min-width:200px;max-width:200px;text-align:center;padding:0px 4px;"><i>'.i18n('raciNoRole').'</i></td>';
  	}
  	$result.='</tr></thead>';

  	$result.='<tbody id="raciMatrixBody">';
  	if (count($functions)>0) {
  	  foreach ($functions as $function) {
  	    $result.=$this->drawRaciFunctionRow($function, $roles, $cellMap, $editable, ($idProject)?true:false);
  	  }
  	} else {
  	  $result.='<tr id="raciNoFunctionRow"><td class="linkData" colspan="'.(($nbRoles>0)?($nbRoles+1):2).'"><i>'.i18n('raciNoFunction').'</i></td></tr>';
  	}
  	if ($idProject and $nbRoles>0) {
  	  $result.=$this->drawAssignmentRow($idProject, $roles);
  	}
  	$result.='</tbody></table>';
  	if ($idProject) {
  	  $result.='</div>';
  	  if ($nbRoles>0) {
  	    $result.='<div style="flex:0 0 275px;">'.$this->drawAvailablePanel($idProject).'</div>';
  	  }
  	  $result.='</div>';
  	}

  	return $result;
  }
  
  public function drawMatrixDashboard($idProject=null) {
    if (!$this->id) return '';
    
    $fnc = new RaciFunction();
    $functions = $fnc->getSqlElementsFromCriteria(array('idRaciModel'=>$this->id), false, null, 'sortOrder asc, name asc');
    
    $rl = new RaciRole();
    $roles = $rl->getSqlElementsFromCriteria(array('idRaciModel'=>$this->id), false, null, 'sortOrder asc, name asc');
    
    $cl = new RaciCell();
    $cells = $cl->getSqlElementsFromCriteria(array('idRaciModel'=>$this->id));
    
    $cellMap = array();
    foreach ($cells as $cell) $cellMap[$cell->idRaciFunction][$cell->idRaciRole] = $cell->value;   
    $assignMap = array();
    if ($idProject) {
      $asg = new RaciAssignment();
      $assignments = $asg->getSqlElementsFromCriteria(array('idProject'=>$idProject, 'idRaciModel'=>$this->id));
      foreach ($assignments as $a) $assignMap[$a->idRaciRole][] = htmlEncode($a->getResourceName());
    }   
    $nbRoles = count($roles);
    
    $firstColStyle = 'position:sticky;left:0;z-index:3;background:#f9fafb;padding:16px;text-align:left;font-size:12px;font-weight:700;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;border-right: 1px solid #e5e7eb;width:220px;min-width:220px;';
    $roleStyle = 'width:120px;min-width:120px;max-width:120px;background:#f9fafb;padding:16px 12px;text-align:center;font-size:12px;font-weight:700;color:#374151;border-bottom:1px solid #e5e7eb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
    $cellStyle = 'width:120px;min-width:120px;max-width:120px;padding:12px;text-align:center;border-bottom:1px solid #f3f4f6;';
    $tagStyle = 'display:inline-block;max-width:110px;padding:5px 10px;margin:3px;background:#fff;border:1px solid #e5e7eb;border-radius:999px;font-size:13px;font-weight:500;color:#374151;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;vertical-align:middle;';
    $nameStyle = 'position:sticky;left:0;width:220px;min-width:220px;max-width:220px;padding:14px 16px;font-size:13px;font-weight:600;color:#374151;border-bottom:1px solid #f3f4f6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
    
    $result = $this->drawRaciLegend(false);    
    $result .= '<div style="margin-top:24px;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#fff;box-shadow:0 4px 20px rgba(0,0,0,.04);">';
    $result .= '';
    $result .= '<div style="overflow-x:auto;">';
    $result .= '<table style="width:100%;table-layout:fixed;border-collapse:separate;border-spacing:0;font-family:Inter,sans-serif;">';
    
    // Header
    $result .= '<thead>';
    $result .= '<tr style="background:#f9fafb;">';
    $result .= '<th style="'.$firstColStyle.'" rowspan="2">'.i18n('raciFunctionColumn').'</th>';
    $role = $nbRoles > 1 ?  i18n('colRoles') : i18n('raciRoleColumn') ; 
    $result .= '<th colspan="'.$nbRoles.'" style="padding:12px 12px 0px 12px;text-align:center;font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#374151;">' .$role.'</th>';
    $result .= '</tr>';
    $result .= '<tr style="background:#ffffff;">';
    foreach ($roles as $role) {
      $result .= '<th style="'.$roleStyle.'">'.htmlEncode($role->name).'</th>';
    }
    $result .= '</tr>';
    
    $result .= '</thead><tbody>';
    // Body
    if (count($functions)) {    
      foreach ($functions as $idx=>$function) {    
        $result .= '<tr onmouseover="this.style.background=\'#f8fafc\';this.querySelector(\'td\').style.background=\'#f8fafc\';" onmouseout="this.style.background=\'white\';this.querySelector(\'td\').style.background=\'white\';">';
        $result .= '<td style="'.$nameStyle.'background:white;">' . htmlEncode($function->name) . '</td>';
        foreach ($roles as $role) {          
          $value = isset($cellMap[$function->id][$role->id]) ? $cellMap[$function->id][$role->id] : '';         
          $result .= '<td style="'.$cellStyle.'">';          
          if ($value) {
            $result .= self::drawRaciBadge($value, self::getValueColor($value), true);
          } else {
            $result .= '<span style="color:#d1d5db;font-size:14px;">—</span>';
          }         
          $result .= '</td>';
        }      
        $result .= '</tr>';
      }     
    } else {     
      $result .= '<tr><td colspan="'.($nbRoles+1).'" style="padding:50px;text-align:center;color:#9ca3af;">'.i18n('raciNoFunction').'</td></tr>';      
    }   
    // Assigned resources
    if ($idProject && $nbRoles) {     
      $result .= '<tr style="background:#f9fafb;">';
      $result .= '<td style="padding:14px 16px;font-weight:700;color:#6b7280;border-top:2px solid #e5e7eb;">'.i18n('raciAssignedResources').'</td>';      
      foreach ($roles as $role) {        
        $result .= '<td style="padding:12px;text-align:center;border-top:2px solid #e5e7eb;vertical-align:top;">';        
        if (!empty($assignMap[$role->id])) {         
          foreach ($assignMap[$role->id] as $name) {
            $result .= '<span title="'.$name.'" style="display:inline-flex;align-items:center;gap:6px;max-width:134px;padding:4px 8px;margin:3px;background:#fff;border:1px solid #e5e7eb;border-radius:999px;vertical-align:middle;">';
            $result .= '<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;flex:0 0 22px;pointer-events:none;">';
            $result .= formatUserThumb($role->id, "", "", 20, 'none');
            $result .= '</span>';
            $result .= '<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;font-weight:500;color:#374151;">'.$name.'</span>';
            $result .= '</span>';
          }          
        } else {        
          $result .= '<span style="color:#d1d5db;font-size:11px;">—</span>';          
        }       
        $result .= '</td>';
      }
     
      $result .= '</tr>';
    }    
    $result .= '</tbody></table></div></div>';   
    return $result;
  }

  private function drawRaciRoleHeaderCell($role, $editable, $projectDisplay=false) {
  	$key=$role->id;
  	$roleName=htmlEncode($role->name);
  	$width=($projectDisplay)?115:200;
  	$whiteSpace=($projectDisplay)?'normal':'nowrap';
  	$result='<td class="assignHeader raciRoleHeaderCell" data-role-key="'.htmlEncode($key).'" style="width:'.$width.'px;min-width:'.$width.'px;max-width:'.$width.'px;white-space:'.$whiteSpace.';padding:3px 8px;word-break:normal;overflow-wrap:break-word;">';
  	if ($editable) {
  	  $result.='<div style="display:flex;align-items:center;gap:6px;">';
  	  $result.='<input type="text" class="input" name="raciRoleName['.htmlEncode($key).']" id="raciRoleName_'.htmlEncode($key).'" value="'.$roleName.'" onchange="formChanged();" oninput="formChanged();" placeholder="'.i18n('raciRoleNamePlaceholder').'" onfocus="raciInputFocus(this);" onblur="raciInputBlur(this);" style="flex:1;min-width:0;width:155px;border:1px solid transparent;border-bottom:1px solid transparent;padding:3px;outline:none;border-radius:2px;text-align:center;" />';
  	  $result.='<a style="flex-shrink:0;" onClick="removeRaciRoleColumn(\''.htmlEncode($key).'\');" title="'.i18n('raciRemoveRole').'">'.formatSmallButton('Remove').'</a>';
  	  $result.='</div>';
  	} else {
  	  $result.='<b style="display:block;text-align:center;white-space:normal;overflow-wrap:break-word;">'.$roleName.'</b>';
  	}
  	$result.='</td>';
  	return $result;
  }

  private function drawRaciFunctionRow($function, $roles, $cellMap, $editable, $projectDisplay=false) {
  	$key=$function->id;
  	$result='<tr class="raciFunctionRow" data-function-key="'.htmlEncode($key).'">';
  	$result.='<td class="linkData" style="width:200px;min-width:200px;max-width:200px;white-space:nowrap;padding:3px 8px;">';
  	if ($editable) {
  	  $result.='<div style="display:flex;align-items:center;gap:6px;">';
  	  $result.='<input type="text" class="input" name="raciFunctionName['.htmlEncode($key).']" id="raciFunctionName_'.htmlEncode($key).'" value="'.htmlEncode($function->name).'" onchange="formChanged();" oninput="formChanged();" placeholder="'.i18n('raciFunctionNamePlaceholder').'" onfocus="raciInputFocus(this);" onblur="raciInputBlur(this);" style="flex:1;min-width:0;width:155px;border:1px solid transparent;border-bottom:1px solid transparent;padding:3px;outline:none;border-radius:2px;" />';
  	  $result.='<a style="flex-shrink:0;" onClick="removeRaciFunctionLine(\''.htmlEncode($key).'\');" title="'.i18n('raciRemoveFunction').'">'.formatSmallButton('Remove').'</a>';
  	  $result.='</div>';
  	} else {
  	  $result.=htmlEncode($function->name);
  	}
  	$result.='</td>';
  	if (count($roles)>0) {
  	  foreach ($roles as $role) {
  	    $value=(isset($cellMap[$function->id][$role->id]))?$cellMap[$function->id][$role->id]:'';
  	    $result.=$this->drawRaciMatrixCell($key, $role->id, $value, $editable, $projectDisplay);
  	  }
  	} else {
  	  $result.='<td class="linkData raciNoRoleDataCell">&nbsp;</td>';
  	}
  	$result.='</tr>';
  	return $result;
  }

  private function drawRaciMatrixCell($functionKey, $roleKey, $value, $editable, $projectDisplay=false) {
  	$color=self::getValueColor($value);
  	$width=($projectDisplay and ! $editable)?100:200;
  	$style='text-align:left;font-weight:normal;width:'.$width.'px;min-width:'.$width.'px;max-width:'.$width.'px;height:30px;vertical-align:middle;'.($color?'background-color:'.$color.';':'');
  	if ($editable) {
  	  $result='<td class="linkData raciMatrixCell" data-function-key="'.htmlEncode($functionKey).'" data-role-key="'.htmlEncode($roleKey).'" style="'.$style.'padding: 0px 5px;" onclick="raciOpenCellSelect(this,true);">';
  	  $result.=$this->drawRaciCellSelect($functionKey, $roleKey, $value);
  	  $result.='</td>';
  	  return $result;
  	}
  	return '<td class="linkData" style="'.$style.'text-align:center;padding:4px;">'.self::drawRaciBadge($value).'</td>';
  }

  private function drawRaciCellSelect($functionKey, $roleKey, $value) {
  	$id='raciCell_'.$functionKey.'_'.$roleKey;
  	$name='raciCell['.$functionKey.']['.$roleKey.']';
  	$options=array(''=>'', 'R'=>'R - '.i18n('raciResponsible'), 'A'=>'A - '.i18n('raciAccountable'), 'C'=>'C - '.i18n('raciConsulted'), 'I'=>'I - '.i18n('raciInformed'));
  	$result='<select dojoType="dijit.form.FilteringSelect" class="input raciCellSelect" name="'.htmlEncode($name).'" id="'.htmlEncode($id).'" onchange="formChanged();" style="width:100%;height:28px;border:none;box-sizing:border-box;" data-dojo-props="queryExpr: \'*${0}*\', autoComplete: true, onFocus: function(){raciOpenCellSelect(this,false);} ">';
  	foreach ($options as $key=>$label) {
  	  $selected=($value==$key)?' selected="selected"':'';
  	  $result.='<option value="'.htmlEncode($key).'"'.$selected.'>'.htmlEncode($label).'</option>';
  	}
  	$result.='</select>';
  	return $result;
  }

  private function drawAvailablePanel($idProject) {
  	$result='<div style="width:275px;margin-bottom:15px;">';
  	$result.='<div class="section" style="width:275px;box-sizing:border-box;margin-bottom:3px;">'.i18n('raciAvailableResources').'</div>';
  	$result.='<div style="position:relative;width:275px;margin-bottom:3px;">';
  	$result.='<input dojoType="dijit.form.TextBox" id="raciAvailableSearch" class="input" style="width:275px;box-sizing:border-box;height: 27px;" value="" onKeyUp="filterDnDList(\'raciAvailableSearch\',\'raciAvailable\');" />';
  	$result.='<div style="position:absolute;right:6px;top:50%;transform:translateY(-50%);" class="iconSearch iconSize16 imageColorNewGuiNoSelection"></div>';
  	$result.='</div>';
  	$result.='<div style="width:275px;box-sizing:border-box;min-height:40px;max-height:145px;overflow:auto;border:1px solid #707070;padding:3px;" id="raciAvailable" dojoType="dojo.dnd.Source" data-dojo-props="accept:[\'raciPerson\'],copyOnly:true">';
  	foreach ($this->getProjectAffectables($idProject) as $affectable) {
  	  $result.=$this->drawAffectableTile($affectable['id'], $affectable['name'], null);
  	}
  	$result.='</div></div>';
  	return $result;
  }

  private function drawAssignmentRow($idProject, $roles) {
  	$asg=new RaciAssignment();
  	$assignments=$asg->getSqlElementsFromCriteria(array('idProject'=>$idProject, 'idRaciModel'=>$this->id));
  	$asgMap=array();
  	foreach ($assignments as $assignment) {
  	  $asgMap[$assignment->idRaciRole][]=$assignment;
  	}
  	$result='<tr>';
  	$result.='<td class="assignHeader" style="width:200px;min-width:200px;max-width:200px;vertical-align:middle;"><b>'.i18n('raciAssignedResources').'</b></td>';
  	foreach ($roles as $role) {
  	  $result.='<td class="linkData" style="vertical-align:top;padding:0;height:1px;">';
  	  $emptyClass=(! isset($asgMap[$role->id]) or count($asgMap[$role->id])==0)?' raciDndEmpty':'';
  	  $result.='<div class="raciRoleDndSource'.$emptyClass.'" dojoType="dojo.dnd.Source" data-dojo-props="accept:[\'raciPerson\']" jsId="raciRoleColumn_'.htmlEncode($role->id).'" id="raciRoleColumn_'.htmlEncode($role->id).'" roleid="'.htmlEncode($role->id).'" style="min-height:50px;height:100%;padding:3px;box-sizing:border-box;">';
  	  if (isset($asgMap[$role->id])) {
  	    foreach ($asgMap[$role->id] as $assignment) {
  	      $result.=$this->drawAffectableTile($assignment->resourceId, $assignment->getResourceName(), $assignment->id, $idProject, 117);
  	    }
  	  }
  	  $result.='</div></td>';
  	}
  	$result.='</tr>';
  	return $result;
  }

  private function drawAffectableTile($idAffectable, $name, $assignId=null, $idProject=null, $fixedWidth=null) {
  	global $print;
  	$widthStyle=($fixedWidth)?'width:'.intval($fixedWidth).'px;box-sizing:border-box;':'';
  	$result='<div class="'.(($print)?'':'dojoDndItem ').'raciPerson" id="raciPerson'.htmlEncode($idAffectable).(($assignId)?'_'.htmlEncode($assignId):'').'" value="'.htmlEncode($name).'" idaffectable="'.htmlEncode($idAffectable).'" '.(($assignId)?'assignid="'.htmlEncode($assignId).'" ':'').'dndType="raciPerson" style="display:flex;align-items:center;'.$widthStyle.'padding:2px 5px;margin:4px;color:#707070;min-height:24px;background-color:#ffffff;border:1px solid #707070;">';
  	$result.='<span title="'.htmlEncode($name).'" style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'.htmlEncode($name).'</span>';
  	$result.='<span style="flex-shrink:0;display:flex;align-items:center;margin-left:4px;">'.formatUserThumb($idAffectable, "", "", 22, 'none').'</span>';
  	if ($assignId and ! $print) {
  	  $result.='<a style="flex-shrink:0;margin-left:4px;" onClick="removeRaciAssignment('.htmlEncode($assignId).','.htmlEncode($this->id).','.htmlEncode($idProject).');" title="'.i18n('raciRemoveAssignment').'">'.formatSmallButton('Remove').'</a>';
  	}
  	$result.='</div>';
  	return $result;
  }

  private function getProjectAffectables($idProject) {
  	$affectables=array();
  	$seen=array();
  	$proj=new Project($idProject,true);
  	$topProjectList=$proj->getTopProjectList(true);
  	if (! $topProjectList or count($topProjectList)==0) $topProjectList=array($idProject);
  	$aff=new Affectation();
  	$where="idProject in ".transformValueListIntoInClause($topProjectList)." and idle=0";
  	$affList=$aff->getSqlElementsFromCriteria(null, false, $where);
  	foreach ($affList as $affectation) {
  	  if (! $affectation->idResource) continue;
  	  if (isset($seen[$affectation->idResource])) continue;
  	  $seen[$affectation->idResource]=true;
  	  $affectable=new Affectable($affectation->idResource);
  	  $name=($affectable->name)?$affectable->name:$affectable->userName;
  	  $affectables[]=array('id'=>$affectation->idResource, 'name'=>$name);
  	}
  	return $affectables;
  }

  public function save() {
  	$result=parent::save();
  	$status=getLastOperationStatus($result);
  	if ($status!='OK' and $status!='NO_CHANGE') return $result;
  	if (! pq_array_key_exists('raciMatrixSubmitted', $_REQUEST)) return $result;
  	$matrixResult=$this->saveRaciMatrixFromRequest();
  	if ($matrixResult) {
  	  $matrixStatus=getLastOperationStatus($matrixResult);
  	  if ($matrixStatus!='OK' and $matrixStatus!='NO_CHANGE') return $matrixResult;
  	  if ($status=='NO_CHANGE' and $matrixStatus=='OK') {
  	    return pq_str_replace(array('NO_CHANGE','messageNO_CHANGE'), array('OK','messageOK'), $result);
  	  }
  	} else if ($status=='NO_CHANGE' and $this->hasEmptyRaciMatrixSubmission()) {
  	  return pq_str_replace(i18n('messageNoChange') . ' ' . i18n(get_class($this)) . ' #' . $this->id, i18n('noDataToSave'), $result);
  	}
  	return $result;
  }

  private function controlRaciMatrixFromRequest() {
  	$result="";
  	$functionNames=(isset($_REQUEST['raciFunctionName']) and is_array($_REQUEST['raciFunctionName']))?$_REQUEST['raciFunctionName']:array();
  	$roleNames=(isset($_REQUEST['raciRoleName']) and is_array($_REQUEST['raciRoleName']))?$_REQUEST['raciRoleName']:array();
  	$cellValues=(isset($_REQUEST['raciCell']) and is_array($_REQUEST['raciCell']))?$_REQUEST['raciCell']:array();
  	foreach ($functionNames as $functionKey=>$functionName) {
  	  if (pq_trim($functionName)!=='') continue;
  	  if ($this->raciFunctionLineHasValue($functionKey, $cellValues)) {
  	    $result.='<br/>'.i18n('raciFunctionNameRequired');
  	    break;
  	  }
  	}
  	foreach ($roleNames as $roleKey=>$roleName) {
  	  if (pq_trim($roleName)!=='') continue;
  	  if ($this->raciRoleColumnHasValue($roleKey, $cellValues)) {
  	    $result.='<br/>'.i18n('raciRoleNameRequired');
  	    break;
  	  }
  	}
  	if ($result=="") $result='OK';
  	return $result;
  }

  private function raciFunctionLineHasValue($functionKey, $cellValues) {
  	if (! isset($cellValues[$functionKey]) or ! is_array($cellValues[$functionKey])) return false;
  	foreach ($cellValues[$functionKey] as $value) {
  	  if ($this->isRaciCellValue($value)) return true;
  	}
  	return false;
  }

  private function raciRoleColumnHasValue($roleKey, $cellValues) {
  	foreach ($cellValues as $roleArray) {
  	  if (! is_array($roleArray)) continue;
  	  if (isset($roleArray[$roleKey]) and $this->isRaciCellValue($roleArray[$roleKey])) return true;
  	}
  	return false;
  }

  private function isRaciCellValue($value) {
  	$value=pq_trim($value);
  	return in_array($value, array('R', 'A', 'C', 'I'));
  }

  private function hasEmptyRaciMatrixSubmission() {
  	$functionNames=(isset($_REQUEST['raciFunctionName']) and is_array($_REQUEST['raciFunctionName']))?$_REQUEST['raciFunctionName']:array();
  	$roleNames=(isset($_REQUEST['raciRoleName']) and is_array($_REQUEST['raciRoleName']))?$_REQUEST['raciRoleName']:array();
  	$hasEmptyLine=false;
  	foreach ($functionNames as $name) {
  	  if (pq_trim($name)==='') $hasEmptyLine=true;
  	}
  	foreach ($roleNames as $name) {
  	  if (pq_trim($name)==='') $hasEmptyLine=true;
  	}
  	return $hasEmptyLine;
  }

  private function isRaciSaveResultOk($result) {
  	$status=getLastOperationStatus($result);
  	return ($status=='OK' or $status=='NO_CHANGE');
  }

  private function saveRaciMatrixFromRequest() {
  	$functionNames=(isset($_REQUEST['raciFunctionName']) and is_array($_REQUEST['raciFunctionName']))?$_REQUEST['raciFunctionName']:array();
  	$roleNames=(isset($_REQUEST['raciRoleName']) and is_array($_REQUEST['raciRoleName']))?$_REQUEST['raciRoleName']:array();
  	$cellValues=(isset($_REQUEST['raciCell']) and is_array($_REQUEST['raciCell']))?$_REQUEST['raciCell']:array();
  	$lastOkResult=null;

  	$functionMap=array();
  	$activeFunctionIds=array();
  	$sortOrder=10;
  	foreach ($functionNames as $key=>$name) {
  	  $name=pq_trim($name);
  	  if ($name==='') continue;
  	  $function=(is_numeric($key))?new RaciFunction($key):new RaciFunction();
  	  if ($function->id and $function->idRaciModel!=$this->id) continue;
  	  $function->idRaciModel=$this->id;
  	  $function->name=$name;
  	  $function->sortOrder=$sortOrder;
  	  $sortOrder+=10;
  	  $res=$function->save();
  	  if (! $this->isRaciSaveResultOk($res)) return $res;
  	  if (getLastOperationStatus($res)=='OK') $lastOkResult=$res;
  	  $functionMap[(string)$key]=$function->id;
  	  $activeFunctionIds[$function->id]=$function->id;
  	}

  	$existingFunction=new RaciFunction();
  	$existingFunctions=$existingFunction->getSqlElementsFromCriteria(array('idRaciModel'=>$this->id));
  	foreach ($existingFunctions as $function) {
  	  if (! isset($activeFunctionIds[$function->id])) {
  	    $res=$this->deleteRaciFunctionWithDependencies($function->id);
  	    if (! $this->isRaciSaveResultOk($res)) return $res;
  	    if (getLastOperationStatus($res)=='OK') $lastOkResult=$res;
  	  }
  	}

  	$roleMap=array();
  	$activeRoleIds=array();
  	$sortOrder=10;
  	foreach ($roleNames as $key=>$name) {
  	  $name=pq_trim($name);
  	  if ($name==='') continue;
  	  $role=(is_numeric($key))?new RaciRole($key):new RaciRole();
  	  if ($role->id and $role->idRaciModel!=$this->id) continue;
  	  $role->idRaciModel=$this->id;
  	  $role->name=$name;
  	  $role->sortOrder=$sortOrder;
  	  $sortOrder+=10;
  	  $res=$role->save();
  	  if (! $this->isRaciSaveResultOk($res)) return $res;
  	  if (getLastOperationStatus($res)=='OK') $lastOkResult=$res;
  	  $roleMap[(string)$key]=$role->id;
  	  $activeRoleIds[$role->id]=$role->id;
  	}

  	$existingRole=new RaciRole();
  	$existingRoles=$existingRole->getSqlElementsFromCriteria(array('idRaciModel'=>$this->id));
  	foreach ($existingRoles as $role) {
  	  if (! isset($activeRoleIds[$role->id])) {
  	    $res=$this->deleteRaciRoleWithDependencies($role->id);
  	    if (! $this->isRaciSaveResultOk($res)) return $res;
  	    if (getLastOperationStatus($res)=='OK') $lastOkResult=$res;
  	  }
  	}

  	$submitted=array();
  	foreach ($cellValues as $functionKey=>$roleArray) {
  	  if (! isset($functionMap[(string)$functionKey]) or ! is_array($roleArray)) continue;
  	  $idFunction=$functionMap[(string)$functionKey];
  	  foreach ($roleArray as $roleKey=>$value) {
  	    if (! isset($roleMap[(string)$roleKey])) continue;
  	    $value=pq_trim($value);
  	    if (! in_array($value, array('', 'R', 'A', 'C', 'I'))) $value='';
  	    $idRole=$roleMap[(string)$roleKey];
  	    $submitted[$idFunction][$idRole]=$value;
  	  }
  	}

  	$cell=new RaciCell();
  	$existingCells=$cell->getSqlElementsFromCriteria(array('idRaciModel'=>$this->id));
  	foreach ($existingCells as $existingCell) {
  	  $idFunction=$existingCell->idRaciFunction;
  	  $idRole=$existingCell->idRaciRole;
  	  $value=(isset($submitted[$idFunction]) and pq_array_key_exists($idRole, $submitted[$idFunction]))?$submitted[$idFunction][$idRole]:'';
  	  if ($value==='') {
  	    $toDelete=new RaciCell($existingCell->id);
  	    $res=$toDelete->delete();
  	    if (! $this->isRaciSaveResultOk($res)) return $res;
  	    if (getLastOperationStatus($res)=='OK') $lastOkResult=$res;
  	  }
  	}

  	foreach ($submitted as $idFunction=>$roleArray) {
  	  foreach ($roleArray as $idRole=>$value) {
  	    if ($value==='') continue;
  	    $existing=SqlElement::getSingleSqlElementFromCriteria('RaciCell', array('idRaciModel'=>$this->id, 'idRaciFunction'=>$idFunction, 'idRaciRole'=>$idRole));
  	    $cell=new RaciCell(($existing and $existing->id)?$existing->id:null);
  	    $cell->idRaciModel=$this->id;
  	    $cell->idRaciFunction=$idFunction;
  	    $cell->idRaciRole=$idRole;
  	    $cell->value=$value;
  	    $res=$cell->save();
  	    if (! $this->isRaciSaveResultOk($res)) return $res;
  	    if (getLastOperationStatus($res)=='OK') $lastOkResult=$res;
  	  }
  	}
  	return $lastOkResult;
  }
  private function deleteRaciFunctionWithDependencies($idFunction) {
  	$cell=new RaciCell();
  	$cell->purge('idRaciFunction='.Sql::fmtId($idFunction));
  	$function=new RaciFunction($idFunction);
  	return $function->delete();
  }

  private function deleteRaciRoleWithDependencies($idRole) {
  	$cell=new RaciCell();
  	$cell->purge('idRaciRole='.Sql::fmtId($idRole));
  	$assign=new RaciAssignment();
  	$assign->purge('idRaciRole='.Sql::fmtId($idRole));
  	$role=new RaciRole($idRole);
  	return $role->delete();
  }

  public function delete() {
  	if ($this->id) {
  	  $crit="idRaciModel=".Sql::fmtId($this->id);
  	  $cell=new RaciCell();        $cell->purge($crit);
  	  $function=new RaciFunction();$function->purge($crit);
  	  $role=new RaciRole();        $role->purge($crit);
  	  $assign=new RaciAssignment(); $assign->purge($crit);
  	}
  	return parent::delete();
  }

}?>



