<?php


class VotingAttributionRuleMain extends SqlElement
{
    public $_sec_description;
    public $id;    // redefine $id to specify its visible place
    public $name;
    public $_spe_refType;
    public $refType;
    public $fixValue;
    public $dailyValue;
    public $weeklyValue;
    public $monthlyValue;
    public $yearlyValue;
    public $limitValue;
    public $idle;

    private static $_fieldsAttributes=array(
        "id"=>"",
        "name"=>"required",
        "refType"=>"",
    );

    private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%" ># ${id}</th>
    <th field="name" width="20%">${name}</th>
    <th field="refType"  width="15%" formatter="translateFormatter">${element}</th>
    <th field="fixValue" formatter="numericFormatter" width="10%">${FixValueVoting}</th>
    <th field="dailyValue" formatter="numericFormatter" width="10%">${dailyValue}</th>
    <th field="weeklyValue" formatter="numericFormatter" width="10%">${weeklyValue}</th>
    <th field="monthlyValue" formatter="numericFormatter" width="10%">${monthlyValue}</th>
    <th field="yearlyValue" formatter="numericFormatter" width="10%">${yearlyValue}</th>
    <th field="limitValue" formatter="numericFormatter" width="5%">${limitValue}</th>
    ';
    
    private static $_colCaptionTransposition = array('fixValue'=>'FixValueVoting','refType'=>'element');
    
    public function __construct($id = NULL, $withoutDependentObjects=false)
    {
      parent::__construct($id,$withoutDependentObjects);
      if ($withoutDependentObjects) return;
    }
    
    public function __destruct() {
      parent::__destruct();
    }
    
    public function control(){
      $result="";
      if (!$this->fixValue and !$this->dailyValue and !$this->weeklyValue and !$this->monthlyValue and !$this->yearlyValue){
        $result .= '<br/>' . i18n ( 'oneValueIsRequiered' );
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
    
    
    /** =========================================================================
     * Draw a specific item for the current class.
     * @param String $item the item.
     * @return String an html string able to display a specific item
     *  must be redefined in the inherited class
     */
    public function drawSpecificItem($item,$readOnly=false,$refresh=false){
      global $largeWidth, $print;
    
      if($item=='refType'){
        self::$_fieldsAttributes['refType']='hidden';
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
          $result .= '  style="width: ' . ($fieldWidth) . 'px;' . $fieldStyle . '"';
          $result .=$name;
          $result .=$attributes;
          $result .=$valStore;
          $result .=autoOpenFilteringSelect();
          $result .=">";
          if (!$isRequired) {
            $result .= '<option value=" " ></option>';
          }
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
    
    
    public function setAttributes() {
      global $contextForAttributes;
      
      if (isset($contextForAttributes) and $contextForAttributes=='global'){
        self::$_fieldsAttributes['refType']='';
      }
      if ($this->fixValue){
        self::$_fieldsAttributes["weeklyValue"]="readonly";
        self::$_fieldsAttributes["monthlyValue"]="readonly";
        self::$_fieldsAttributes["yearlyValue"]="readonly";
        self::$_fieldsAttributes["dailyValue"]="readonly";
      }
      if($this->weeklyValue){
        self::$_fieldsAttributes["fixValue"]="readonly";
        self::$_fieldsAttributes["monthlyValue"]="readonly";
        self::$_fieldsAttributes["yearlyValue"]="readonly";
        self::$_fieldsAttributes["dailyValue"]="readonly";
      }
      if($this->monthlyValue){
        self::$_fieldsAttributes["fixValue"]="readonly";
        self::$_fieldsAttributes["weeklyValue"]="readonly";
        self::$_fieldsAttributes["yearlyValue"]="readonly";
        self::$_fieldsAttributes["dailyValue"]="readonly";
      }
      if($this->yearlyValue){
        self::$_fieldsAttributes["fixValue"]="readonly";
        self::$_fieldsAttributes["weeklyValue"]="readonly";
        self::$_fieldsAttributes["monthlyValue"]="readonly";
        self::$_fieldsAttributes["dailyValue"]="readonly";
      }
      if($this->dailyValue){
        self::$_fieldsAttributes["fixValue"]="readonly";
        self::$_fieldsAttributes["weeklyValue"]="readonly";
        self::$_fieldsAttributes["monthlyValue"]="readonly";
        self::$_fieldsAttributes["yearlyValue"]="readonly";
      }
    }
    
    
    public function getValidationScript($colName) {
      $colScript = parent::getValidationScript ( $colName );
      if ($colName == "fixValue") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' if(dijit.byId("fixValue").get("value")){';
        $colScript .= '   dijit.byId("weeklyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("monthlyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("yearlyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("dailyValue").set("readOnly",true);';
        $colScript .= ' }else{ '; 
        $colScript .= '   dijit.byId("weeklyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("monthlyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("yearlyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("dailyValue").set("readOnly",false);';
        $colScript .= ' } ';
        $colScript .= '</script>';
      } else if ($colName == "weeklyValue") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' if(dijit.byId("weeklyValue").get("value")){';
        $colScript .= '   dijit.byId("fixValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("monthlyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("yearlyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("dailyValue").set("readOnly",true);';
        $colScript .= ' }else{ '; 
        $colScript .= '   dijit.byId("fixValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("monthlyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("yearlyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("dailyValue").set("readOnly",false);';
        $colScript .= ' } ';
        $colScript .= '</script>';
      } else if ($colName == "monthlyValue") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' if(dijit.byId("monthlyValue").get("value")){';
        $colScript .= '   dijit.byId("weeklyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("fixValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("yearlyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("dailyValue").set("readOnly",true);';
        $colScript .= ' }else{ '; 
        $colScript .= '   dijit.byId("weeklyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("fixValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("yearlyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("dailyValue").set("readOnly",false);';
        $colScript .= ' } ';
        $colScript .= '</script>';
      } else if ($colName == "yearlyValue") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' if(dijit.byId("yearlyValue").get("value")){';
        $colScript .= '   dijit.byId("weeklyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("monthlyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("fixValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("dailyValue").set("readOnly",true);';
        $colScript .= ' }else{ '; 
        $colScript .= '   dijit.byId("weeklyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("monthlyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("fixValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("dailyValue").set("readOnly",false);';
        $colScript .= ' } ';
        $colScript .= '</script>';
      } else if ($colName == "dailyValue") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' if(dijit.byId("dailyValue").get("value")){';
        $colScript .= '   dijit.byId("weeklyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("monthlyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("yearlyValue").set("readOnly",true);';
        $colScript .= '   dijit.byId("fixValue").set("readOnly",true);';
        $colScript .= ' }else{ '; 
        $colScript .= '   dijit.byId("weeklyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("monthlyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("yearlyValue").set("readOnly",false);';
        $colScript .= '   dijit.byId("fixValue").set("readOnly",false);';
        $colScript .= ' } ';
        $colScript .= '</script>';
      } 
      return $colScript;
    }
    
    
    public function save() {
      $result = parent::save();
      return $result;
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

    /** ==========================================================================
     * Return the specific layout
     * @return String the layout
     */
    protected function getStaticLayout() {
      return self::$_layout;
    }
    
}