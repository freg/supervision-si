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
 * Client is the owner of a project.
 */  
require_once('_securityCheck.php'); 
class ClientMain extends SqlElement {

  // extends SqlElement, so has $id
  public $_sec_Description;
  public $id;    // redefine $id to specify its visiblez place 
  public $name;
  public $idClientType;
  public $idProspectQualification;
  public $idDomainProspect;
  public $idLanguage;
  public $clientCode;
  public $idPaymentDelay;
  public $taxPct;
  public $companyNumber;
  public $numTax;
  public $idStatus;
  public $idResource;
  public $idle;
  public $description;
  public $_sec_Address;
  public $designation;
  public $street;
  public $complement;
  public $zip;
  public $city;
  public $state;
  public $country;
  public $_sec_Projects;
  public $_spe_projects;
  public $_sec_Contacts;
  public $_spe_contacts;
  public $_sec_AttributionVote;
  public $_spe_attributionVote;
  public $_spe_situation;
  public $_sec_QuotationsList;
  public $_spe_Quotation;
  public $_sec_CommandsList;
  public $_spe_Command;
  public $_sec_BillsList;
  public $_spe_Bill;
  public $_sec_TicketsClient;
  public $_spe_tickets;
  public $_sec_loyaltyEvent;
  public $_spe_ProspectEvent;
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();
  public $_nbColMax=3;
  
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%"># ${id}</th>
    <th field="name" width="30%">${clientName}</th>
  	<th field="nameClientType" width="15%">${idClientType}</th> 
    <th field="clientCode" width="15%">${clientCode}</th> 
    <th field="namePaymentDelay" width="15%">${paymentDelay}</th>
    <th field="taxPct" width="5%" formatter="percentSimpleFormatter">${tax}</th>
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';
  
  private static $_colCaptionTransposition = array('name'=> 'clientName', 'idPaymentDelay'=>'paymentDelay', 'idResource'=>'responsible');
  private static $_fieldsAttributes=array(
      'name'=>'required',
      'idClientType'=>'required'
  );
  private static $_databaseColumnName = array('taxPct'=>'tax');
  
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
  
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
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
  
  /** =========================================================================
   * Draw a specific item for the current class.
   * @param String $item the item. Correct values are : 
   *    - subprojects => presents sub-projects as a tree
   * @return String an html string able to display a specific item
   *  must be redefined in the inherited class
   */
  public function drawSpecificItem($item){
    global $print;
    $result="";
    if ($item=='projects') {
      $prj=new Project();
      $result .="<table><tr><td class='label' valign='top'><label>" . i18n('projects') . "&nbsp;:&nbsp;</label>";
      $result .="</td><td>";
      if ($this->id) {
        $result .= $prj->drawProjectsList(array('idClient'=>$this->id,'idle'=>'0'));
      }
      $result .="</td></tr></table>";
      return $result;
    } else if ($item=='contacts') {
      $con=new Contact();
      if ($this->id) {
        $result .= $con->drawContactsList(array('idClient'=>$this->id,'idle'=>'0'));
      }
      return $result;
    }else if ($item=='Quotation' or $item=="Command" or $item=="Bill"){
      $result .= drawClientElementList($item, $this);
      return $result;
    }else if($item=='attributionVote'){
      if($this->id){
        $votingAttr = new VotingAttribution();
        $critArray=array('idClient'=>$this->id);
        $list = $votingAttr->getSqlElementsFromCriteria($critArray);
        drawAttributionVote($this,$list);
        return $result;
      }
    } else if ($item=='ProspectEvent') {
      // The client shows its own actions and those of its contacts. That is an
      // alternative, which an array of criteria cannot express : hence the clause.
      // The contact column tells apart the actions that name one.
      $idCli=intval($this->id??0);
      ProspectEvent::drawList($this, array(), true,
        "(refType='Client' AND refId=$idCli)"
       ." OR idContact IN (SELECT id FROM resource WHERE isContact=1 AND idClient=$idCli)");
    }
  }
  public function setAttributes() {
    if (Parameter::getGlobalParameter('manageTicketCustomer') != 'YES') {
      self::$_fieldsAttributes["_sec_TicketsClient"]='hidden';
      self::$_fieldsAttributes["_spe_tickets"]='hidden';
    }
    $clientElementList = Parameter::getUserParameter('clientElementList');
    if($clientElementList == 'false' or !$this->id){
      self::$_fieldsAttributes['_sec_QuotationsList']='hidden';
      self::$_fieldsAttributes['_sec_CommandsList']='hidden';
      self::$_fieldsAttributes['_sec_BillsList']='hidden';
    }
    if(! Module::isModuleActive('moduleCrmProspect') ){ 
       self::$_fieldsAttributes['_sec_loyaltyEvent']='hidden';
       self::$_fieldsAttributes['_spe_ProspectEvent']='hidden';
    }
  }
  
}
?>