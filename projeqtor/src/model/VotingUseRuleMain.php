<?php


class VotingUseRuleMain extends SqlElement
{
    public $_sec_description;
    public $id;    // redefine $id to specify its visible place
    public $name;
    public $idProject;
    public $_spe_refType;
    public $refType;
    public $idType;
    public $idUser;
    public $blocking__idStatus;
    public $workPointConvertion;
    public $fixValue;
    public $maxPointsPerUser;
    public $isDownVoting;
    public $idle;
    
    
      private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="name" width="20%">${name}</th>
    <th field="nameProject" width="20%">${idProject}</th>
    <th field="refType" formatter="translateFormatter" width="15%">${element}</th>
    <th field="nameType" width="20%">${type}</th>
    <th field="nameStatus" width="20%">${blockingStatus}</th>
    ';
    
    private static $_fieldsAttributes=array(
        "id"=>"",
        "name"=>"required",
        "refType"=>"",
        "blocking__idStatus"=>"notInList",
    );

    private static $_colCaptionTransposition = array('blocking__idStatus' => 'blockingStatus','idType'=>'type','fixValue'=>'FixValueVoting','refTyme'=>'element');
    
  /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }
    
    private static $_databaseColumnName = array('blocking__idStatus' => 'idStatus' );
    
    public function __destruct() {
      parent::__destruct();
    }
    
    public function control(){
      $result="";
      if(!$this->fixValue and !$this->workPointConvertion)$result .= '<br/>' . i18n ( 'VotingUseRuleMainMustHaveFixOrWorkPoint' );
      $array = array('refType'=>$this->refType,'idProject'=>$this->idProject,'idType'=>$this->idType);
      $voting = $this->getSingleSqlElementFromCriteria('VotingUseRule', $array);
      $exist = false;
      if($voting->id and $voting->id != $this->id)$exist=true;
      if($exist)$result .= '<br/>' . i18n ( 'VotingUseRuleMainAlreadyExist' );
      $defaultControl=parent::control();
      if ($defaultControl!='OK') {
        $result.=$defaultControl;
      }
      if ($result=="") {
        $result='OK';
      }
      return $result;
    }
    
    
    private static $_fieldsTooltip = array(
        "workPointConvertion"=> "hintWorkPointConvertion"
    );
    
    public function setAttributes() {
      // Fetch data to set attributes only to display user. Other access to User (for History) don't need these attributes.
      if($this->workPointConvertion and $this->workPointConvertion > 0){
        self::$_fieldsAttributes["fixValue"]="readonly";
      }
      if($this->fixValue and $this->fixValue >0){
        self::$_fieldsAttributes["workPointConvertion"]="readonly";
      }
    }
    
    /** =========================================================================
     * Draw a specific item for the current class.
     * @param String $item the item.
     * @return String an html string able to display a specific item
     *  must be redefined in the inherited class
     */
    public function drawSpecificItem($item,$readOnly=false,$refresh=false){
      global $largeWidth, $print;
      self::$_fieldsAttributes['refType']='hidden';
      if($item=='refType'){
        $votingItem = new VotingItem();
        $arrayClassWithDateTypeFields=$votingItem->getVotableClassList();
        $fieldAttributes=$this->getFieldAttributes($item);
        if(pq_strpos($fieldAttributes,'required')!==false) {
          $isRequired = true;
        } else {
          $isRequired = false;
        }
        $notReadonlyClass=($readOnly?"":" generalColClassNotReadonly ");
        $notRequiredClass=($isRequired?"":" generalColClassNotRequired ");
        $style=$this->getDisplayStyling($item);
        $attReadOnly=($readOnly?"readonly":"");
        $fieldWidth=$largeWidth;
        $labelStyle=$style["caption"];
        $fieldStyle=$style["field"];
        $colScript='';
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= '  dijit.byId("idType").set("value","");';
        $colScript .= '  refreshList("idType","scope", this.value);';
        $colScript .= '  formChanged();';
        $colScript .= '</script>';
        $extName="";
        $name=' id="_spe_' . $item . '" name="_spe_' . $item . $extName . '" ';
        $attributes =' required="true" missingMessage="' . i18n('messageMandatory', array($this->getColCaption($item))) . '" invalidMessage="' . i18n('messageMandatory', array($this->getColCaption($item))) . '"';
        $valStore='';
        $result  = '<tr class="detail generalRowClass">';
        $result .= '<td class="tabLabel" style="text-align:right;font-weight:normal">' . i18n("colElement");
        $result .= '</td>';
        if (!$print) {
          $result .= '<td>';
          $result .= '<select '.$attReadOnly.' dojoType="dijit.form.FilteringSelect" class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$item.'Class" xlabelType="html" ';
          $result .= '  style="border-left:3px solid #FF0000 !important;width: ' . ($fieldWidth-12) . 'px;' . $fieldStyle . '"';
          $result .=$name;
          $result .=$attributes;
          $result .=$valStore;
          $result .=autoOpenFilteringSelect();
          $result .=">";
          foreach ($arrayClassWithDateTypeFields as $key => $value) {
            $result .= '<option value="' . $value . '"';
            if($this->id and $value === $this->refType) {
              $result .= ' SELECTED ';
            }
            $result .= '><span >'. htmlEncode(i18n($value)) . '</span></option>';
          }
    
          $result .=$colScript;
          $result .="</select></td>";
        } else {
          $result .= '<td style="color:grey;'.$fieldStyle.'">' . i18n($this->refType) . "&nbsp;&nbsp;&nbsp;</td>";
        }
        $result .= '</tr>';
        return $result;
      }
    }
    
    public function getValidationScript($colName) {
      $colScript = parent::getValidationScript ( $colName );
     if($colName == "fixValue"){
        $colScript .= '<script type="dojo/connect" event="onChange" >';
          $colScript .= ' if(dijit.byId("fixValue").get("value")){ ';
        $colScript .= '   dijit.byId("workPointConvertion").set("readOnly",true);';
        $colScript .= '   dijit.byId("workPointConvertion").set("value",null);';
        $colScript .= '  }else{ ';
        $colScript .= '   dijit.byId("workPointConvertion").set("readOnly",false);';
        $colScript .= '  }';
        $colScript .= '</script>';
      }elseif($colName == "workPointConvertion"){
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' if(dijit.byId("workPointConvertion").get("value")){ ';
        $colScript .= '   dijit.byId("fixValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("fixValue").set("value",null);';
        $colScript .= '  }else{ ';
        $colScript .= '   dijit.byId("fixValue").set("readOnly",false);';
        $colScript .= '  }';
        $colScript .= '</script>';
      }
      return $colScript;
    }
    
    public function save() {
      $result = parent::save();
      return $result;
    }
    
    /** ==========================================================================
     * Return the specific layout
     * @return String the layout
     */
    protected function getStaticLayout() {
      return self::$_layout;
    }
    
  
    
    /**
     * ========================================================================
     * Return the specific databaseColumnName
     *
     * @return String the databaseTableName
     */
    protected function getStaticDatabaseColumnName() {
      return self::$_databaseColumnName;
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
    
    protected function getStaticFieldsTooltip() {
      return self::$_fieldsTooltip;
    }

}