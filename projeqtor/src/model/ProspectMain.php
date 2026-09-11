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
//test
/** ============================================================================
 * Action is establised during meeting, to define an action to be followed.
 */ 
require_once('_securityCheck.php'); 
class ProspectMain extends SqlElement {
  
  public $_sec_description;
  public $id;
  public $name;
  public $idUser;
  public $prospectNameContact;
  public $prospectNameCompany;
  public $idProspectType;
  public $idProspectionSource;
  public $idProspectQualification;
  public $idProspectOrigin;
  public $idDomainProspect;
  public $idLanguage;
  public $idEngagement;
  public $prospectFunction;
  public $idPositionProspect;
  public $idDecisionMakerProspect;
  public $description; 
  public $_sec_Contact;
  public $email;
  public $phone;
  public $mobile;
  public $fax;
  public $networkLink; 
  public $_sec_Address;
  public $designation;
  public $street;
  public $complement;
  public $zip;
  public $city;
  public $state;
  public $country;
  public $_sec_treatment;
  public $idStatus;
  public $idResource;
  public $idle;
  public $_multiple_ProspectEvent;
  public $_spe_buttonTransform;
  public $lastEventDatetime;
  public $toBeRecontacted;
  public $_sec_eventProspect;
  public $_spe_ProspectEvent;
  public $_sec_ProspectEstimateList;
  public $_spe_ProspectEstimate;
  public $_sec_Link_Prospect;
  public $_Link_Prospect=array();
  //public $_sec_Link_Client;
  //public $_Link_Client=array();
  //public $_sec_Link_Contact;
  //public $_Link_Contact=array();
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();
  public $_nbColMax=3;

  private static $_fieldsAttributes=array(
    "id"=>"",
    "idProspectType"=>"required",
    "idProspectionSource"=>"required",
    "lastEventDatetime"=>"readonly",
    "idle"=>"",
    "name"=>"hidden",
    "idStatus"=>"required",
    "prospectNameContact"=>"",
    "_multiple_ProspectEvent"=>"hidden",
  );
  
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%"># ${id}</th>
    <th field="name" width="30%" >${name}</th>
    <th field="nameProspectionSource" width="10%">${idProspectionSource}</th>
    <th field="nameProspectOrigin" width="15%">${idProspectOrigin}</th>
    <th field="nameDecisionMakerProspect" width="10%">${idDecisionMakerProspect}</th>
    <th field="colorNameStatus" formatter="colorNameFormatter" width="10%">${idStatus}</th>
    <th field="lastEventDatetime" formatter="dateFormatter" width="10%">${lastEventDatetime}</th>
    <th field="toBeRecontacted" formatter="dateFormatter" width="10%">${toBeRecontacted}</th>
    ';
  
  private static $_colCaptionTransposition = array('idResource'=> 'responsible');
  
  private static $_databaseColumnName = array();
 
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

	/** ==========================================================================
	 * Return the specific layout
	 * @return String the layout
	 */
	
	protected function getStaticLayout() {
	  return self::$_layout;
	}
	
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return array_merge(parent::getStaticFieldsAttributes(),self::$_fieldsAttributes);
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }
  
  /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
 
  /** ============================================================================
   * Set attribut from parent : merge current attributes with those of Main class
   * @return void
   */
  public function setAttributes() {
    if (!$this->id) {
      self::$_fieldsAttributes['_sec_ProspectEstimateList']='hidden';
      self::$_fieldsAttributes['_spe_ProspectEstimate']='hidden';
    }
	} 
  
// ============================================================================**********
// GET VALIDATION SCRIPT
// ============================================================================**********

/** ==========================================================================
 * Return the validation sript for some fields
 * @return String the validation javascript (for dojo framework)
 */
public function getValidationScript($colName, $date=null) {
  $colScript = parent::getValidationScript($colName);

    if ($colName=="idProspectionSource") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= '  refreshList("idProspectOrigin", "idProspectionSource", this.value, null, null, false);';
        $colScript .= '  formChanged();';
        $colScript .= '</script>';
    } 
    return $colScript;
    
} 
  public function save() {
      $this->name=$this->prospectNameCompany.(($this->prospectNameCompany and $this->prospectNameContact)?' | ':'').$this->prospectNameContact; 
      $result = parent::save();
      return $result;
	} 
  
	public function control(){
	  $result="";
	
	  if (pq_trim($this->prospectNameContact)=='' and pq_trim($this->prospectNameCompany)=='') {
	    $result.='<br/>' . i18n('messageMandatory',array(i18n('colProspectNameContact') . ' ' .i18n('OR'). ' '.i18n('colProspectNameCompany')));
	  }
	  
	
	  $defaultControl=parent::control();
	  if ($defaultControl!='OK') {
	    $result.=$defaultControl;
	  }if ($result=="") {
	    $result='OK';
	  }
	  return $result;
	}
	
  public function drawSpecificItem($item){
    global $print;
    
    $result="";
    if ($item=='ProspectEstimate') {
      $result .= drawProspectEstimateList($this);
      return $result;
    }
    if ($item=='buttonTransform' and $this->id) {
      $lnk=new Link();
      $cpt=$lnk->countSqlElementsFromCriteria(null,"ref2Type='Prospect' and ref2Id=$this->id and (ref1Type='Contact' or ref1Type='Client')");
      if ($cpt==0) {
        $result .= '<tr><td valign="top" class="label"><label></label></td><td>';
        $result .= '<button style="height:71% !important;" class="dynamicTextButton" id="prospectTransform" dojoType="dijit.form.Button" showlabel="true" onClick ="saveProspectTransform('.$this->id.')"';
        $result .= ' title="' . i18n('buttonTransformTitle') . '" >';
        $result .= '<span>' . i18n('buttonTransform') . '</span>';
        $result .= '</button>';
        $result .= '</td></tr>';
      }
    } else if ($item=='ProspectEvent') {
      // No contact column on a prospect : its actions never carry one.
      ProspectEvent::drawList($this, array('refType'=>'Prospect', 'refId'=>($this->id??'0')), false);
    }
    return $result;
  }
  
  

	
}
?>