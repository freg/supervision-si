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
 * Menu defines list of items to present to users.
 */

require_once('_securityCheck.php');

class EmailTemplate extends SqlElement {
    
    public $_sec_description;
    public $id;
    public $name;
    public $idMailable;
    public $idType;
    public $title;
    public $idle;
    //public $_sec_message;
    public $template;
    //public $_sec_void;
    //Damian
    public $_spe_listItemTemplate;
    //public $_spe_buttonInsertInTemplate;
    
    private static $_fieldsAttributes=array("idMailable"=>"",
        "idType"=>"nocombo",
        "name"=>"required",
        "template"=>"required"
    );  
    private static $_colCaptionTransposition = array(
        'idType' => 'type'
    );
    private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="name" width="60%" >${name}</th>
    <th field="nameMailable" width="15%" formatter="nameFormatter">${idMailable}</th>
    <th field="nameType" width="15%" formatter="nameFormatter">${type}</th>
    <th field="idle" width="5%" formatter="booleanFormatter" >${idle}</th>
    ';
    
    
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
    
    // ============================================================================**********
    // GET STATIC DATA FUNCTIONS
    // ============================================================================**********
    
    /** ==========================================================================
     * Return the specific layout
     * @return String the layout
     */
    protected function getStaticLayout() {
      return self::$_layout;
    }
    /** ============================================================================
     * Return the specific colCaptionTransposition
     * @return String the colCaptionTransposition
     */
    protected function getStaticColCaptionTransposition($fld=null) {
      return self::$_colCaptionTransposition;
    }
    
    protected function getStaticFieldsAttributes() {
      return self::$_fieldsAttributes;
    }
    
    public function getValidationScript($colName) {
      
      $colScript = parent::getValidationScript($colName);
      
      if ($colName=='idMailable') {
        $colScript .= '<script type="dojo/connect" event="onChange" args="evt">';
        $colScript .= '  dijit.byId("idType").set("value",null);';
        $colScript .= '  refreshList("idType","scope", mailableArray[this.value]);';
        $colScript .= '  refreshListFieldsInTemplate(dijit.byId("idMailable").get("value"));';
        $colScript .= '  formChanged();';
        $colScript .= '</script>';
        $colScript .= '<script type="dojo/connect" event="onLoad" args="evt">';
        $colScript .= '  refreshListFieldsInTemplate(dijit.byId("idMailable").get("value"));';
        $colScript .= '  formChanged();';
        $colScript .= '</script>';
      }
      
      return $colScript;
    }
    
    
    private function getMailableItem() {
      $mailableItem = null;
    	if ($this->id) {
    		$mailableItem = new Mailable($this->idMailable);
    	}
    	return $mailableItem;
    }
    
    public function drawListItem($item,$readOnly=false,$refresh=false) {
      global $largeWidth, $print, $toolTip, $outMode;
      
      if ($print or $outMode=="pdf" or $readOnly) {
      	return("");
      }
      
      $itemLab = "listFieldsTitle";
      $itemEnd = pq_str_replace("listItem","", $item);
      
      $arrayFields = array();
      $newArrayFields = array();
      if($this->getMailableItem() != null){
        $mailableItem=$this->getMailableItem();
        if ($mailableItem->id != null) {
        	$nameMailableItem = SqlList::getFieldFromId('Mailable', $mailableItem->id, 'name',false);
        	$arrayFields = getObjectClassTranslatedFieldsList(pq_trim($nameMailableItem));
        	foreach ($arrayFields as $elmt=>$val){
        		$newArrayFields[$elmt]=$val;
        		if(pq_substr($elmt, 0, 2) == "id" and pq_substr($elmt, 2) != "" and $elmt != "idle" and $elmt != "idleDateTime"){
        			$newArrayFields['name'.pq_ucfirst(pq_substr($elmt, 2))]=$val.' ('.i18n('colName').')';
        		}
        		//gautier #4046
        		if($mailableItem->name=="Ticket"){
        		  if($elmt=='WorkElement'){
        		    $arrayFields2 = getObjectClassTranslatedFieldsList(pq_trim($elmt));
        		    foreach ($arrayFields2 as $elmt2=>$val2){
        		      $newArrayFields['WorkElement_'.$elmt2]=$val2;
        		    }
        		  }
        		}
        		if($elmt=='VotingItem'){
        		  $arrayFields2 = getObjectClassTranslatedFieldsList(pq_trim($elmt));
        		  foreach ($arrayFields2 as $elmt2=>$val2){
        		    $newArrayFields['VotingItem_'.$elmt2]=$val2;
        		  }
        		}
        		if($mailableItem->name=="Activity" or $mailableItem->name=="Project" or $mailableItem->name=="Milestone" or $mailableItem->name=="Meeting" or $mailableItem->name=="TestSession"){
        		    $arrayFields2 = getObjectClassTranslatedFieldsList($mailableItem->name.'PlanningElement');
        		    foreach ($arrayFields2 as $elmt2=>$val2){
        		      if($elmt2=='paused' or $elmt2=='fixPlanning')continue;
        		      $newArrayFields['PlanningElement_'.$elmt2]=$val2;
        		    }
        		}
        	}
        }else{
          $newArrayFields['_id'] = 'id';
          $newArrayFields['_name'] = i18n('colName');
          $newArrayFields['_idProject'] = 'id'.i18n('colIdProject');
          $newArrayFields['_nameProject'] = i18n('colIdProject').' ('.i18n('colName').')';
          $newArrayFields['_description'] = 'colDescription';
        }
      }else{
        $newArrayFields['_id'] = 'id';
        $newArrayFields['_name'] = i18n('colName');
        $newArrayFields['_idProject'] = 'id'.i18n('colIdProject');
        $newArrayFields['_nameProject'] = i18n('colIdProject').' ('.i18n('colName').')';
        $newArrayFields['_description'] = 'colDescription';
      }
      $newArrayFields['_item'] = i18n('mailableItem');
      $newArrayFields['_dbName'] = i18n('mailableDbName');
      $newArrayFields['_responsible'] = i18n('colResponsible').', '.i18n('synonymResponsible');
      $newArrayFields['_sender'] = i18n('mailableSender');
      $newArrayFields['_project'] = i18n('colIdProject').', '.i18n('synonymProject');
      $newArrayFields['_url'] = i18n('mailableUrl');
      $newArrayFields['_goto'] = i18n('mailableGoto');
      $newArrayFields['_HISTORY'] = i18n('mailableHistory');
      $newArrayFields['_HISTORYFULL'] = i18n('mailableHistoryFull');
      $newArrayFields['_LINK'] = i18n('mailableLink');
      $newArrayFields['_NOTE'] = i18n('mailableNote');
      $newArrayFields['_NOTESTD'] = i18n('mailableNoteTd');
      $newArrayFields['_allAttachments'] = i18n('mailableAttachments');
      $newArrayFields['_lastAttachment'] = i18n('mailableLastAttachments');
      if($this->getMailableItem() != null){
        if($mailableItem->name=="Meeting" OR $mailableItem->name=="TestSession" OR $mailableItem->name=="Activity"){
          $newArrayFields['ASSIGNMENT'] = i18n('colListAssignment');
        }
      }
      $arrayFields = $newArrayFields;
      $sortArray = array();
      foreach ($arrayFields as $key=>$name){
        $pregName = htmlentities($name, ENT_NOQUOTES, 'utf-8');
        $pregName = preg_replace('#&([A-za-z])(?:uml|circ|tilde|acute|grave|cedil|ring);#', '\1', $pregName);
        $pregName = preg_replace('#&([A-za-z]{2})(?:lig);#', '\1', $pregName);
        $pregName = preg_replace('#&[^;]+;#', '', $pregName);
      	$sortArray[$key] = pq_strtolower($pregName);
      }
      asort($sortArray);
      foreach ($arrayFields as $key=>$name){
        $sortArray[$key]=$name;
      }
      $arrayFields = $sortArray;
      $fieldAttributes=$this->getFieldAttributes($item);
      if(pq_strpos($fieldAttributes,'required')!==false) {
      	$isRequired = true;
      } else {
      	$isRequired = false;
      }
      $notReadonlyClass=($readOnly?"":" generalColClassNotReadonly ");
      $notRequiredClass=($isRequired?"":" generalColClassNotRequired ");
      $style=$this->getDisplayStyling($item);
      $labelStyle=$style["caption"];
      $fieldStyle=$style["field"];
      $fieldWidth=$largeWidth;
      $extName="";
      $fullItem = "_spe_$item";
      $name=' id="' . $fullItem . '" name="' . $fullItem . $extName . '" ';
      $attributes =' required="true" missingMessage="' . i18n('messageMandatory', array($this->getColCaption($itemLab))) . '" invalidMessage="' . i18n('messageMandatory', array($this->getColCaption($item))) . '"';
      
      //$colScript  = '';
      
      $result  = '<table><tr class="detail generalRowClass">';
      $result .= '<td class="label" style="font-weight:normal;"><label>' . i18n("col".pq_ucfirst($itemLab));
      $result .= '&nbsp;:&nbsp;</label></td>';
      $result .= '<td>';
      $result .= '<select dojoType="dijit.form.Select" class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$item.'Class"';
      $result .= '  style="width: ' . ($fieldWidth-150) . 'px;' . $fieldStyle . '; "';
      $result .= $name;
      $result .=$attributes;
      $result .=">";
      
      $first=true;
      foreach ($arrayFields as $key => $value) {
      	$result .= '<option value="' . $key . '"';
      	if($first) {
      		$result .= ' selected="selected" ';
      		$first=false;
      	}
      	$result .= '> <span>'. htmlEncode($value) . '</span>
      	            </option>';
      }
      //$result .=$colScript;
      $result .="</select>";
      $itemEnd = pq_str_replace("buttonAddIn","", $item);
      $editor = getEditorType();
      $textBox = pq_strtolower($itemEnd);;
      $result .= '<button id="_spe_listItemTemplate_button" class="roundedVisibleButton" dojoType="dijit.form.Button" showlabel="true" style="position:relative;min-width:100px;'.((isNewGui())?'top:0;':'top:-2px;height:17px;width:145px;').'">';
      $result .= i18n('operationInsert');
      $result .= '<script type="dojo/connect" event="onClick" args="evt">';
      $result .= '  addFieldInTextBoxForEmailTemplateItem("'.$editor.'");';
      $result .= '  formChanged();';
      $result .= '</script>';
      $result .= '</button>';
      $result .='</td>';
      $result .= '</tr></table>';
      return $result;
    }

    
    public function drawSpecificItem($item,$readOnly=false,$refresh=false){
      if ($item=='listItemTemplate') {
      	return $this->drawListItem($item, $readOnly, $refresh);
      } 
      return "";
    }
    
    public function control(){
      $result="";
      if(pq_strpos($this->template,'${lastAttachment}')and pq_strpos($this->template, '${allAttachments}')){
        $result=i18n('onlyOne',array('${lastAttachment}/${allAttachments}'));
      }else if(mb_substr_count ($this->template,'${lastAttachment}')>1 or mb_substr_count ($this->template, '${allAttachments}')>1){
        $var='${lastAttachment}';
        if(pq_strpos($this->template,'${allAttachments}')){
          $var='${allAttachments}';
        }
        $result=i18n('onlyOne',array($var));
      }      
      if ($result=="") {
        $result='OK';
      }
      return $result;
    }
    
}